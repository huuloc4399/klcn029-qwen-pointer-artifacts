"""Deployment acceptance policy layered on top of frozen Pointer Parser v1.

Parser v1 remains immutable for benchmark comparability.  Real CVs may contain
explicit soft skills outside the synthetic stage-1 allowlist.  The deployment
layer accepts those values when the pointer/schema contracts remain valid and
can also remove a duplicated, clearly soft skill from ``hard_skills``.
"""

from __future__ import annotations

import copy
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


DEPLOYMENT_ACCEPTANCE_POLICY_VERSION = "real_cv_skills_v3_2026-10-07"

_SOFT_SKILL_MARKERS = (
    "active listening",
    "adaptability",
    "attention to detail",
    "collaboration",
    "communication",
    "critical thinking",
    "interpersonal",
    "leadership",
    "listening",
    "presentation",
    "problem solving",
    "problem-solving",
    "responsibility",
    "team work",
    "teamwork",
    "time management",
    "willingness to learn",
    "chu dong",
    "giai quyet van de",
    "giao tiep",
    "hoc hoi",
    "hop tac",
    "kha nang lam viec nhom",
    "ky nang lam viec nhom",
    "lam viec nhom",
    "lang nghe",
    "lanh dao",
    "quan ly thoi gian",
    "thich nghi",
    "thuyet trinh",
    "trach nhiem",
    "tu duy phan bien",
)


@dataclass(frozen=True)
class DeploymentAcceptanceDecision:
    accepted: bool
    mode: str
    policy_version: str
    warnings: tuple[str, ...]
    rejection_reason: str | None = None
    normalizations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        payload["normalizations"] = list(self.normalizations)
        return payload


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_marks.split())


def _looks_like_soft_skill(value: str) -> bool:
    normalized = _normalize_text(value)
    return any(marker in normalized for marker in _SOFT_SKILL_MARKERS)


def _skill_lists(result: Any) -> tuple[list[str], list[str]]:
    schema = getattr(result, "reconstructed_cvschema", None)
    if not isinstance(schema, dict):
        return [], []
    skills = schema.get("skills")
    if not isinstance(skills, dict):
        return [], []
    hard = [value for value in skills.get("hard_skills", []) if isinstance(value, str)]
    soft = [value for value in skills.get("soft_skills", []) if isinstance(value, str)]
    return hard, soft


def _repairable_soft_overlaps(result: Any) -> tuple[str, ...] | None:
    hard, soft = _skill_lists(result)
    hard_by_key = {_normalize_text(value): value for value in hard}
    soft_keys = {_normalize_text(value) for value in soft}
    overlaps = tuple(hard_by_key[key] for key in sorted(set(hard_by_key) & soft_keys))
    if overlaps and not all(_looks_like_soft_skill(value) for value in overlaps):
        return None
    return overlaps


def _accepted_skill_policy_shape(issues: list[Any], *, allow_overlap: bool) -> bool:
    if not issues:
        return False
    for issue in issues:
        if getattr(issue, "code", None) != "skill_policy":
            return False
        message = str(getattr(issue, "message", ""))
        fragments = [fragment.strip() for fragment in message.split(";") if fragment.strip()]
        allowed_prefixes = ["disallowed_soft_skills="]
        if allow_overlap:
            allowed_prefixes.append("hard_soft_overlap=")
        if not fragments or not all(any(fragment.startswith(prefix) for prefix in allowed_prefixes) for fragment in fragments):
            return False
    return True


def assess_pointer_result(result: Any) -> DeploymentAcceptanceDecision:
    """Return a deterministic decision without modifying Parser v1 output."""

    structurally_valid = all(
        (
            bool(getattr(result, "pointer_schema_valid", False)),
            bool(getattr(result, "span_contract_valid", False)),
            bool(getattr(result, "cvschema_valid", False)),
            getattr(result, "reconstructed_cvschema", None) is not None,
            getattr(result, "evidence", None) is not None,
        )
    )
    if not structurally_valid:
        return DeploymentAcceptanceDecision(
            accepted=False,
            mode="rejected",
            policy_version=DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
            warnings=(),
            rejection_reason="pointer_span_or_cvschema_invalid",
        )

    issues = list(getattr(result, "issues", ()))
    if getattr(result, "status", None) == "success" and not issues:
        return DeploymentAcceptanceDecision(
            accepted=True,
            mode="parser_v1_strict",
            policy_version=DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
            warnings=(),
        )

    repairable_overlaps = _repairable_soft_overlaps(result)
    allow_overlap = repairable_overlaps is not None and bool(repairable_overlaps)
    if _accepted_skill_policy_shape(issues, allow_overlap=allow_overlap):
        if allow_overlap:
            return DeploymentAcceptanceDecision(
                accepted=True,
                mode="real_cv_skills_normalized",
                policy_version=DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
                warnings=(
                    "Frozen Parser v1 found a duplicated hard/soft skill. The deployment "
                    "layer kept the clearly soft skill only in soft_skills.",
                    "Frozen Parser v1 flagged its synthetic-only soft-skill allowlist; "
                    "CVSchema and source evidence remain valid.",
                ),
                normalizations=tuple(
                    f"removed_from_hard_skills:{_normalize_text(value)}"
                    for value in repairable_overlaps
                ),
            )
        return DeploymentAcceptanceDecision(
            accepted=True,
            mode="real_cv_soft_skills_expanded",
            policy_version=DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
            warnings=(
                "Frozen Parser v1 flagged its synthetic-only soft-skill allowlist; "
                "CVSchema and source evidence remain valid.",
            ),
        )

    return DeploymentAcceptanceDecision(
        accepted=False,
        mode="rejected",
        policy_version=DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
        warnings=(),
        rejection_reason="non_legacy_policy_or_other_parser_issue",
    )


def normalized_cvschema_for_deployment(
    result: Any,
    decision: DeploymentAcceptanceDecision | None = None,
) -> dict[str, Any] | None:
    """Return a copy of the accepted schema with safe deployment repairs applied."""

    decision = decision or assess_pointer_result(result)
    schema = getattr(result, "reconstructed_cvschema", None)
    if not decision.accepted or not isinstance(schema, dict):
        return None

    normalized_schema = copy.deepcopy(schema)
    skills = normalized_schema.get("skills")
    if not isinstance(skills, dict):
        return normalized_schema

    soft_keys = {
        _normalize_text(value)
        for value in skills.get("soft_skills", [])
        if isinstance(value, str)
    }
    if decision.mode == "real_cv_skills_normalized":
        skills["hard_skills"] = [
            value
            for value in skills.get("hard_skills", [])
            if not (
                isinstance(value, str)
                and _normalize_text(value) in soft_keys
                and _looks_like_soft_skill(value)
            )
        ]
    return normalized_schema
