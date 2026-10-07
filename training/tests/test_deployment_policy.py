from types import SimpleNamespace

from training.evaluation.deployment_policy import (
    assess_pointer_result,
    normalized_cvschema_for_deployment,
)


def result(*, status="needs_review", issues=(), structural=True, hard=(), soft=()):
    return SimpleNamespace(
        status=status,
        issues=issues,
        pointer_schema_valid=structural,
        span_contract_valid=structural,
        cvschema_valid=structural,
        reconstructed_cvschema={
            "skills": {"hard_skills": list(hard), "soft_skills": list(soft)}
        } if structural else None,
        evidence={} if structural else None,
    )


def issue(code, message):
    return SimpleNamespace(code=code, message=message)


def test_accepts_strict_parser_success():
    decision = assess_pointer_result(result(status="success"))
    assert decision.accepted and decision.mode == "parser_v1_strict"


def test_accepts_only_expanded_real_cv_soft_skills():
    decision = assess_pointer_result(
        result(issues=(issue("skill_policy", "disallowed_soft_skills=['adaptability', 'problem-solving']"),))
    )
    assert decision.accepted and decision.mode == "real_cv_soft_skills_expanded"


def test_accepts_and_normalizes_clear_soft_skill_overlap():
    decision = assess_pointer_result(
        result(
            issues=(issue(
                "skill_policy",
                "hard_soft_overlap=['khả năng làm việc nhóm']; "
                "disallowed_soft_skills=['khả năng làm việc nhóm']",
            ),),
            hard=("Python", "Khả năng làm việc nhóm"),
            soft=("Khả năng làm việc nhóm",),
        )
    )
    assert decision.accepted and decision.mode == "real_cv_skills_normalized"
    normalized = normalized_cvschema_for_deployment(
        result(
            issues=(issue("skill_policy", "hard_soft_overlap=['khả năng làm việc nhóm']"),),
            hard=("Python", "Khả năng làm việc nhóm"),
            soft=("Khả năng làm việc nhóm",),
        ),
        decision,
    )
    assert normalized["skills"]["hard_skills"] == ["Python"]
    assert normalized["skills"]["soft_skills"] == ["Khả năng làm việc nhóm"]


def test_rejects_technical_skill_overlap():
    decision = assess_pointer_result(
        result(
            issues=(issue("skill_policy", "hard_soft_overlap=['python']; disallowed_soft_skills=['python']"),),
            hard=("Python",),
            soft=("Python",),
        )
    )
    assert not decision.accepted


def test_rejects_wrong_communication_group_without_safe_overlap():
    decision = assess_pointer_result(
        result(issues=(issue("skill_policy", "communication_is_hard"),), hard=("Communication",))
    )
    assert not decision.accepted


def test_rejects_schema_or_span_failures():
    assert not assess_pointer_result(result(structural=False)).accepted


def test_rejects_any_non_policy_issue():
    decision = assess_pointer_result(result(issues=(issue("span_out_of_range", "bad span"),)))
    assert not decision.accepted
