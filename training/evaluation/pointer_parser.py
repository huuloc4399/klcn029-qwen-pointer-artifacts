"""Deterministic parser and reconstructor for CVPointerSchema 1.0.

This module is the boundary between the Pointer model and the frozen CVSchema
parser contract. It validates output without inventing values or repairing
truncated JSON, reconstructs long text from source lines, and returns field-level
diagnostics that can later drive selective retry.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError

from baseline_extraction.schema import CVSchema
from training.evaluation.parser import (
    JSONContractError,
    remove_known_wrappers,
    strict_json_loads,
    validate_stage1_skill_policy,
)


POINTER_PARSER_VERSION = "cvpointer_output_parser_v1"
POINTER_SCHEMA_VERSION = "1.0"
SOURCE_SCHEMA_VERSION = "2.0"

ROOT_KEYS = frozenset(
    {
        "personal_info",
        "summary_span",
        "skills",
        "experience",
        "projects",
        "education",
        "certifications",
        "activities",
        "awards",
    }
)
PERSONAL_KEYS = frozenset({"name", "email", "phone", "github_url"})
SKILL_KEYS = frozenset({"hard_skills", "soft_skills"})
EXPERIENCE_KEYS = frozenset(
    {"company", "job_title", "duration", "description_span"}
)
PROJECT_KEYS = frozenset({"name", "role", "technologies", "details_span"})
EDUCATION_KEYS = frozenset({"degree", "university", "gpa", "year_graduated"})

POINTER_PARSER_CONTRACT: dict[str, Any] = {
    "parser_version": POINTER_PARSER_VERSION,
    "pointer_schema_version": POINTER_SCHEMA_VERSION,
    "output_schema_version": SOURCE_SCHEMA_VERSION,
    "line_policy": "one-based non-empty stripped source lines",
    "span_policy": "inclusive [start_line, end_line] or null",
    "json_repair": False,
    "truncated_output_repair": False,
    "missing_field_imputation": False,
    "reconstruction": "deterministic newline join",
    "downstream_contract": "validated CVSchema 2.0 plus evidence sidecar",
}


@dataclass(frozen=True)
class PointerIssue:
    code: str
    field: str
    message: str
    category: str
    retryable: bool = True


@dataclass(frozen=True)
class PointerParseResult:
    parser_version: str
    status: str
    strict_json: bool
    recoverable_json: bool
    recovery_steps: tuple[str, ...]
    parsed_pointer: dict[str, Any] | None
    pointer_schema_valid: bool
    span_contract_valid: bool
    reconstructed_cvschema: dict[str, Any] | None
    cvschema_valid: bool
    skill_policy_valid: bool
    evidence: dict[str, Any] | None
    retry_targets: tuple[str, ...]
    issues: tuple[PointerIssue, ...]
    strict_error: str | None
    recovery_error: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recovery_steps"] = list(self.recovery_steps)
        payload["retry_targets"] = list(self.retry_targets)
        payload["issues"] = [asdict(issue) for issue in self.issues]
        return payload


def source_lines(source_text: str) -> list[str]:
    """Use the same line contract as the Pointer dataset converter."""

    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    return [line.strip() for line in source_text.splitlines() if line.strip()]


def _add_issue(
    issues: list[PointerIssue],
    code: str,
    field: str,
    message: str,
    category: str,
    *,
    retryable: bool = True,
) -> None:
    issues.append(
        PointerIssue(
            code=code,
            field=field,
            message=message,
            category=category,
            retryable=retryable,
        )
    )


def _validate_keys(
    value: Any,
    expected: frozenset[str],
    field: str,
    issues: list[PointerIssue],
) -> bool:
    if not isinstance(value, dict):
        _add_issue(
            issues,
            "object_type",
            field,
            f"expected object, got {type(value).__name__}",
            "schema",
        )
        return False
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        _add_issue(
            issues,
            "missing_keys",
            field,
            f"missing keys: {missing}",
            "schema",
        )
    if extra:
        _add_issue(
            issues,
            "extra_keys",
            field,
            f"extra keys: {extra}",
            "schema",
        )
    return not missing and not extra


def _validate_string(value: Any, field: str, issues: list[PointerIssue]) -> None:
    if not isinstance(value, str):
        _add_issue(
            issues,
            "string_type",
            field,
            f"expected string, got {type(value).__name__}",
            "schema",
        )


def _validate_string_list(value: Any, field: str, issues: list[PointerIssue]) -> None:
    if not isinstance(value, list):
        _add_issue(
            issues,
            "array_type",
            field,
            f"expected array, got {type(value).__name__}",
            "schema",
        )
        return
    for index, item in enumerate(value):
        _validate_string(item, f"{field}[{index}]", issues)


def _validate_span(
    value: Any,
    field: str,
    line_count: int,
    issues: list[PointerIssue],
) -> None:
    if value is None:
        return
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        _add_issue(
            issues,
            "span_type",
            field,
            "expected null or exactly two integer line numbers",
            "schema",
        )
        return
    start, end = value
    if start < 1:
        _add_issue(
            issues,
            "span_start_before_first_line",
            field,
            f"start={start}, minimum=1",
            "span",
        )
    if end < start:
        _add_issue(
            issues,
            "span_reversed",
            field,
            f"start={start}, end={end}",
            "span",
        )
    if end > line_count:
        _add_issue(
            issues,
            "span_end_after_last_line",
            field,
            f"end={end}, line_count={line_count}",
            "span",
        )


def validate_pointer_document(
    value: Any, line_count: int
) -> tuple[PointerIssue, ...]:
    """Validate CVPointerSchema shape and source-dependent span constraints."""

    if not isinstance(line_count, int) or isinstance(line_count, bool) or line_count < 1:
        raise ValueError("line_count must be a positive integer")

    issues: list[PointerIssue] = []
    if not _validate_keys(value, ROOT_KEYS, "$", issues):
        if not isinstance(value, dict):
            return tuple(issues)

    personal = value.get("personal_info")
    if _validate_keys(personal, PERSONAL_KEYS, "personal_info", issues):
        for key in PERSONAL_KEYS:
            _validate_string(personal[key], f"personal_info.{key}", issues)
        for key in ("name", "email", "phone"):
            if isinstance(personal[key], str) and personal[key] != "[MASKED]":
                _add_issue(
                    issues,
                    "pii_not_masked",
                    f"personal_info.{key}",
                    "training/evaluation contract requires [MASKED]",
                    "policy",
                    retryable=False,
                )

    _validate_span(value.get("summary_span"), "summary_span", line_count, issues)

    skills = value.get("skills")
    if _validate_keys(skills, SKILL_KEYS, "skills", issues):
        _validate_string_list(skills["hard_skills"], "skills.hard_skills", issues)
        _validate_string_list(skills["soft_skills"], "skills.soft_skills", issues)

    experience = value.get("experience")
    if not isinstance(experience, list):
        _add_issue(
            issues,
            "array_type",
            "experience",
            f"expected array, got {type(experience).__name__}",
            "schema",
        )
    else:
        for index, item in enumerate(experience):
            path = f"experience[{index}]"
            if not _validate_keys(item, EXPERIENCE_KEYS, path, issues):
                if not isinstance(item, dict):
                    continue
            for key in ("company", "job_title", "duration"):
                _validate_string(item.get(key), f"{path}.{key}", issues)
            _validate_span(
                item.get("description_span"),
                f"{path}.description_span",
                line_count,
                issues,
            )

    projects = value.get("projects")
    if not isinstance(projects, list):
        _add_issue(
            issues,
            "array_type",
            "projects",
            f"expected array, got {type(projects).__name__}",
            "schema",
        )
    else:
        for index, item in enumerate(projects):
            path = f"projects[{index}]"
            if not _validate_keys(item, PROJECT_KEYS, path, issues):
                if not isinstance(item, dict):
                    continue
            for key in ("name", "role"):
                _validate_string(item.get(key), f"{path}.{key}", issues)
            _validate_string_list(item.get("technologies"), f"{path}.technologies", issues)
            _validate_span(
                item.get("details_span"),
                f"{path}.details_span",
                line_count,
                issues,
            )

    education = value.get("education")
    if not isinstance(education, list):
        _add_issue(
            issues,
            "array_type",
            "education",
            f"expected array, got {type(education).__name__}",
            "schema",
        )
    else:
        for index, item in enumerate(education):
            path = f"education[{index}]"
            if not _validate_keys(item, EDUCATION_KEYS, path, issues):
                if not isinstance(item, dict):
                    continue
            for key in ("degree", "university"):
                _validate_string(item.get(key), f"{path}.{key}", issues)
            gpa = item.get("gpa")
            if gpa is not None and (
                not isinstance(gpa, (int, float)) or isinstance(gpa, bool)
            ):
                _add_issue(
                    issues,
                    "number_or_null_type",
                    f"{path}.gpa",
                    f"expected number or null, got {type(gpa).__name__}",
                    "schema",
                )
            year = item.get("year_graduated")
            if year is not None and (
                not isinstance(year, int) or isinstance(year, bool)
            ):
                _add_issue(
                    issues,
                    "integer_or_null_type",
                    f"{path}.year_graduated",
                    f"expected integer or null, got {type(year).__name__}",
                    "schema",
                )

    for field in ("certifications", "activities", "awards"):
        _validate_string_list(value.get(field), field, issues)

    return tuple(issues)


def _span_text(lines: list[str], span: list[int] | None) -> str:
    if span is None:
        return ""
    start, end = span
    return "\n".join(lines[start - 1 : end])


def reconstruct_pointer_document(
    pointer: dict[str, Any], source_text: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct CVSchema 2.0 and an evidence sidecar from a valid pointer."""

    lines = source_lines(source_text)
    issues = validate_pointer_document(pointer, len(lines))
    if issues:
        raise ValueError(
            "pointer is invalid: "
            + "; ".join(f"{item.field}:{item.code}" for item in issues)
        )

    result = copy.deepcopy(pointer)
    evidence: dict[str, Any] = {}

    summary_span = result.pop("summary_span")
    result["summary"] = _span_text(lines, summary_span)
    evidence["summary"] = {
        "span": summary_span,
        "text": result["summary"],
    }

    for index, item in enumerate(result["experience"]):
        span = item.pop("description_span")
        item["description"] = _span_text(lines, span)
        evidence[f"experience[{index}].description"] = {
            "span": span,
            "text": item["description"],
        }

    for index, item in enumerate(result["projects"]):
        span = item.pop("details_span")
        item["details"] = _span_text(lines, span)
        evidence[f"projects[{index}].details"] = {
            "span": span,
            "text": item["details"],
        }

    return result, evidence


def _parse_json_output(
    raw_output: str,
) -> tuple[Any | None, bool, bool, tuple[str, ...], str | None, str | None]:
    stripped = raw_output.strip()
    strict_error: str | None = None
    recovery_error: str | None = None
    recovery_steps: tuple[str, ...] = ()
    try:
        return strict_json_loads(stripped), True, True, (), None, None
    except (json.JSONDecodeError, JSONContractError) as error:
        strict_error = str(error)
        candidate, recovery_steps = remove_known_wrappers(raw_output)
        try:
            parsed = strict_json_loads(candidate)
            return (
                parsed,
                False,
                True,
                recovery_steps,
                strict_error,
                None,
            )
        except (json.JSONDecodeError, JSONContractError) as recovery_exception:
            recovery_error = str(recovery_exception)
            return (
                None,
                False,
                False,
                recovery_steps,
                strict_error,
                recovery_error,
            )


def parse_pointer_output(raw_output: str, source_text: str) -> PointerParseResult:
    """Parse, validate, reconstruct and validate one Pointer model response."""

    if not isinstance(raw_output, str):
        raise TypeError("raw_output must be a string")
    lines = source_lines(source_text)
    if not lines:
        raise ValueError("source_text has no non-empty lines")

    (
        parsed,
        strict_json,
        recoverable_json,
        recovery_steps,
        strict_error,
        recovery_error,
    ) = _parse_json_output(raw_output)

    issues: list[PointerIssue] = []
    reconstructed: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    cvschema_valid = False
    skill_policy_valid = False

    if parsed is None:
        _add_issue(
            issues,
            "json_not_recoverable",
            "$",
            recovery_error or strict_error or "unknown JSON error",
            "json",
        )
        parsed_pointer = None
        pointer_schema_valid = False
        span_contract_valid = False
        status = "failed"
    else:
        pointer_issues = validate_pointer_document(parsed, len(lines))
        issues.extend(pointer_issues)
        parsed_pointer = copy.deepcopy(parsed) if isinstance(parsed, dict) else None
        pointer_schema_valid = not any(
            issue.category in {"schema", "policy"} for issue in issues
        )
        span_contract_valid = pointer_schema_valid and not any(
            issue.category == "span" for issue in issues
        )

        if pointer_schema_valid and span_contract_valid and parsed_pointer is not None:
            reconstructed, evidence = reconstruct_pointer_document(
                parsed_pointer, source_text
            )
            try:
                resume = CVSchema.model_validate(reconstructed)
                reconstructed = resume.model_dump(mode="json")
                cvschema_valid = True
                skill_policy_valid, policy_error = validate_stage1_skill_policy(resume)
                if not skill_policy_valid:
                    _add_issue(
                        issues,
                        "skill_policy",
                        "skills",
                        policy_error or "skill policy failed",
                        "policy",
                        retryable=False,
                    )
            except ValidationError as error:
                _add_issue(
                    issues,
                    "cvschema_validation",
                    "$",
                    str(error),
                    "output_schema",
                )

        status = (
            "success"
            if cvschema_valid and skill_policy_valid and not issues
            else "needs_review"
        )

    retry_targets = tuple(
        dict.fromkeys(issue.field for issue in issues if issue.retryable)
    )
    return PointerParseResult(
        parser_version=POINTER_PARSER_VERSION,
        status=status,
        strict_json=strict_json,
        recoverable_json=recoverable_json,
        recovery_steps=recovery_steps,
        parsed_pointer=parsed_pointer,
        pointer_schema_valid=pointer_schema_valid,
        span_contract_valid=span_contract_valid,
        reconstructed_cvschema=reconstructed,
        cvschema_valid=cvschema_valid,
        skill_policy_valid=skill_policy_valid,
        evidence=evidence,
        retry_targets=retry_targets,
        issues=tuple(issues),
        strict_error=strict_error,
        recovery_error=recovery_error,
    )

