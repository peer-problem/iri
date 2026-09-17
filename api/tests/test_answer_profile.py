import pytest

from api.app.answer_profile import ANSWER_PROFILE


def test_answer_profile_v1_has_one_complete_model_independent_configuration():
    assert ANSWER_PROFILE.version == "v1"
    assert ANSWER_PROFILE.guidance
    assert ANSWER_PROFILE.behavior_examples
    assert set(ANSWER_PROFILE.fallbacks) == {
        "redirect",
        "support",
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
