import pytest

from api.app.answer_profile import ANSWER_PROFILE
from api.app.service import FALLBACKS


def test_answer_profile_v1_has_one_complete_model_independent_configuration():
    assert ANSWER_PROFILE.version == "v1"
    assert ANSWER_PROFILE.guidance
    assert ANSWER_PROFILE.behavior_examples
    assert set(ANSWER_PROFILE.fallbacks) == {
        "redirect",
        "support",
        "support_followup",
        "clarify",
        "unavailable",
    }
    assert "[AnswerProfile v1]" in ANSWER_PROFILE.prompt
    assert "정답이 아니라 행동 방식을 참고" in ANSWER_PROFILE.prompt
    assert "Kanana" not in ANSWER_PROFILE.prompt
    assert "Luna" not in ANSWER_PROFILE.prompt


def test_answer_profile_fallbacks_are_immutable():
    with pytest.raises(TypeError):
        ANSWER_PROFILE.fallbacks["redirect"] = "changed"


def test_service_fallbacks_have_one_source_and_follow_v1_response_order():
    assert FALLBACKS is ANSWER_PROFILE.fallbacks

    redirect = FALLBACKS["redirect"]
    assert redirect.index("멈추고") < redirect.index("떨어져서") < redirect.index("어른")

    support = FALLBACKS["support"]
    assert support.index("네 잘못이 아니야") < support.index("다친 곳")
    assert support.index("다친 곳") < support.index("안전해")
    assert FALLBACKS["support_followup"] != support

    assert FALLBACKS["clarify"] == "어떤 걸 말하는지 조금만 더 알려 줄래?"
