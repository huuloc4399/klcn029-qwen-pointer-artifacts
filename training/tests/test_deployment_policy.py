from types import SimpleNamespace

from training.evaluation.deployment_policy import assess_pointer_result


def result(*, status="needs_review", issues=(), structural=True):
    return SimpleNamespace(
        status=status,
        issues=issues,
        pointer_schema_valid=structural,
        span_contract_valid=structural,
        cvschema_valid=structural,
        reconstructed_cvschema={} if structural else None,
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


def test_rejects_overlap_or_wrong_communication_group():
    decision = assess_pointer_result(
        result(issues=(issue("skill_policy", "disallowed_soft_skills=['teamwork']; communication_is_hard"),))
    )
    assert not decision.accepted


def test_rejects_schema_or_span_failures():
    assert not assess_pointer_result(result(structural=False)).accepted


def test_rejects_any_non_policy_issue():
    decision = assess_pointer_result(result(issues=(issue("span_out_of_range", "bad span"),)))
    assert not decision.accepted
