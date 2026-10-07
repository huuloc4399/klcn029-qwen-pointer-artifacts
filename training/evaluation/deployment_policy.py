"""Deployment acceptance policy layered on top of frozen Pointer Parser v1.

Parser v1 remains immutable for benchmark comparability.  This policy only
allows structurally valid real-CV outputs that Parser v1 rejected solely because
the synthetic stage-1 contract allowed Communication as the only soft skill.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEPLOYMENT_ACCEPTANCE_POLICY_VERSION = "real_cv_soft_skills_v2_2026-10-07"


@dataclass(frozen=True)
class DeploymentAcceptanceDecision:
    accepted: bool
    mode: str
    policy_version: str
    warnings: tuple[str, ...]
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def _is_only_legacy_soft_skill_rejection(issues: list[Any]) -> bool:
    if not issues:
        return False
    for issue in issues:
        if getattr(issue, "code", None) != "skill_policy":
            return False
        message = str(getattr(issue, "message", ""))
        fragments = [fragment.strip() for fragment in message.split(";") if fragment.strip()]
        if not fragments or not all(
            fragment.startswith("disallowed_soft_skills=") for fragment in fragments
        ):
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

    if _is_only_legacy_soft_skill_rejection(issues):
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
