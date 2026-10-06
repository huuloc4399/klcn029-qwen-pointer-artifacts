"""Deterministic parser for Qwen CVSchema 2.0 output.

The parser intentionally performs no JSON repair. It may only remove complete,
known wrappers at the beginning or around the whole response. Truncated JSON,
prose, missing braces, trailing prose, and malformed values remain failures.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError

from baseline_extraction.schema import CVSchema


PARSER_VERSION = "cvschema2_output_parser_v1"
SKILL_POLICY_VERSION = "rpv_skills_v1_reviewed_2026-09-23"
ALLOWED_SOFT_SKILLS = frozenset({"communication"})

PARSER_CONTRACT: dict[str, Any] = {
    "parser_version": PARSER_VERSION,
    "schema_version": "2.0",
    "skill_policy_version": SKILL_POLICY_VERSION,
    "strict_json": "json.loads with duplicate keys and NaN/Infinity rejected",
    "recovery_order": [
        "complete leading <think>...</think> blocks",
        "one or more leading </tool_call> tags",
        "one whole-response Markdown json fence",
    ],
    "json_repair": False,
    "balanced_object_extraction": False,
    "trailing_text_removal": False,
    "truncated_output_repair": False,
    "allowed_soft_skills_normalized": sorted(ALLOWED_SOFT_SKILLS),
    "hard_soft_overlap_allowed": False,
}


class JSONContractError(ValueError):
    """Raised when input uses a non-interoperable JSON construct."""


def _reject_json_constant(value: str) -> None:
    raise JSONContractError(f"non_standard_json_constant={value}")


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JSONContractError(f"duplicate_json_key={key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    return json.loads(
        text,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_object_keys,
    )


@dataclass(frozen=True)
class ParseResult:
    parser_version: str
    strict_json: bool
    recoverable_json: bool
    recovery_steps: tuple[str, ...]
    parsed_value: Any | None
    strict_error: str | None
    recovery_error: str | None
    schema_valid: bool
    schema_error: str | None
    skill_policy_valid: bool
    skill_policy_error: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recovery_steps"] = list(self.recovery_steps)
        return payload


def normalize_skill(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(normalized.split())


def _strip_leading_think_blocks(text: str) -> tuple[str, bool]:
    candidate = text.lstrip()
    changed = False
    while candidate.startswith("<think>"):
        closing_index = candidate.find("</think>", len("<think>"))
        if closing_index < 0:
            break
        candidate = candidate[closing_index + len("</think>") :].lstrip()
        changed = True
    return candidate, changed


def _strip_leading_tool_call_closers(text: str) -> tuple[str, bool]:
    candidate = re.sub(r"^(?:\s*</tool_call>\s*)+", "", text)
    return candidate, candidate != text


def _strip_whole_markdown_fence(text: str) -> tuple[str, bool]:
    match = re.fullmatch(
        r"\s*```(?:json)?\s*\n?(.*?)\n?```\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return text, False
    return match.group(1).strip(), True


def remove_known_wrappers(raw_output: str) -> tuple[str, tuple[str, ...]]:
    """Remove only complete wrappers approved by PARSER_CONTRACT."""

    candidate = raw_output.strip()
    recovery_steps: list[str] = []

    candidate, changed = _strip_leading_think_blocks(candidate)
    if changed:
        recovery_steps.append("leading_think")

    candidate, changed = _strip_leading_tool_call_closers(candidate)
    if changed:
        recovery_steps.append("leading_tool_call_close")

    candidate, changed = _strip_whole_markdown_fence(candidate)
    if changed:
        recovery_steps.append("markdown_fence")

    return candidate, tuple(recovery_steps)


def validate_stage1_skill_policy(resume: CVSchema) -> tuple[bool, str | None]:
    hard = [normalize_skill(skill) for skill in resume.skills.hard_skills]
    soft = [normalize_skill(skill) for skill in resume.skills.soft_skills]
    overlap = sorted(set(hard) & set(soft))
    disallowed_soft = sorted(
        skill for skill in set(soft) if skill not in ALLOWED_SOFT_SKILLS
    )
    communication_in_hard = "communication" in set(hard)

    errors = []
    if overlap:
        errors.append(f"hard_soft_overlap={overlap}")
    if disallowed_soft:
        errors.append(f"disallowed_soft_skills={disallowed_soft}")
    if communication_in_hard:
        errors.append("communication_is_hard")
    return (not errors, "; ".join(errors) if errors else None)


def _validate_schema(value: Any) -> tuple[CVSchema | None, str | None]:
    try:
        return CVSchema.model_validate(value), None
    except ValidationError as error:
        return None, str(error)


def parse_cvschema_output(raw_output: str) -> ParseResult:
    """Parse one raw response and validate CVSchema 2.0 plus stage-1 skills."""

    if not isinstance(raw_output, str):
        raise TypeError("raw_output must be a string")

    stripped = raw_output.strip()
    strict_error: str | None = None
    recovery_error: str | None = None
    recovery_steps: tuple[str, ...] = ()

    try:
        parsed_value = strict_json_loads(stripped)
        strict_json = True
        recoverable_json = True
    except (json.JSONDecodeError, JSONContractError) as error:
        strict_json = False
        strict_error = str(error)
        candidate, recovery_steps = remove_known_wrappers(raw_output)
        try:
            parsed_value = strict_json_loads(candidate)
            recoverable_json = True
        except (json.JSONDecodeError, JSONContractError) as recovery_exception:
            parsed_value = None
            recoverable_json = False
            recovery_error = str(recovery_exception)

    if parsed_value is None:
        schema_valid = False
        schema_error = "json_not_recoverable"
        skill_policy_valid = False
        skill_policy_error = "schema_invalid"
    else:
        resume, schema_error = _validate_schema(parsed_value)
        schema_valid = resume is not None
        if resume is None:
            skill_policy_valid = False
            skill_policy_error = "schema_invalid"
        else:
            skill_policy_valid, skill_policy_error = validate_stage1_skill_policy(resume)
            # Use the schema-normalized JSON representation for stable downstream metrics.
            parsed_value = resume.model_dump(mode="json")

    return ParseResult(
        parser_version=PARSER_VERSION,
        strict_json=strict_json,
        recoverable_json=recoverable_json,
        recovery_steps=recovery_steps,
        parsed_value=parsed_value,
        strict_error=strict_error,
        recovery_error=recovery_error,
        schema_valid=schema_valid,
        schema_error=schema_error,
        skill_policy_valid=skill_policy_valid,
        skill_policy_error=skill_policy_error,
    )
