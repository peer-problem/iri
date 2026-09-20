import pytest
from pydantic import ValidationError

from api.app.settings import Settings
from api.app.speech_contract import (
    compact_speech_text,
    segment_speech_text,
    verify_spoken_text,
)


def configuration(**updates):
    return Settings(_env_file=None, **updates)


def test_default_speech_profile_favors_fewer_voice_resets():
    settings = configuration()

    assert settings.tts_voice == "marin"
    assert settings.tts_speed == 1.0
    assert settings.tts_segment_max_chars == 240
    assert "캐릭터를 연기하지 말고" in settings.tts_instructions


@pytest.mark.parametrize(
    "text",
    [
        "짧은 문장이야.",
        "첫 문장이야. 두 번째 문장이야! 마지막 질문일까?",
        "첫 줄이야.\n둘째 줄이야.\n마지막 줄이야.",
        "친구가 “오늘은 같이 읽자.”라고 말했고, 나는 천천히 고개를 끄덕였어.",
        "숫자 1, 2, 3과 무지개 🌈를 읽은 뒤 마지막 말을 해 줘.",
    ],
)
def test_segmentation_preserves_all_spoken_content(text):
    segments = segment_speech_text(text, max_chars=36, max_segments=12)
    assert segments
    assert all(len(segment) <= 36 for segment in segments)
    assert compact_speech_text("".join(segments)) == compact_speech_text(text)


def test_segmentation_prefers_natural_boundaries_for_long_korean_text():
    text = (
        "같이 놀기 싫을 때는 거절해도 괜찮고, 직접 말하기 어렵다면 혼자 참지 말고, "
        "믿을 만한 어른에게 그대로 말해도 돼."
    )
    segments = segment_speech_text(text, max_chars=42, max_segments=12)
    assert segments == [
        "같이 놀기 싫을 때는 거절해도 괜찮고,",
        "직접 말하기 어렵다면 혼자 참지 말고,",
        "믿을 만한 어른에게 그대로 말해도 돼.",
    ]


def test_segmentation_rejects_unbounded_segment_count():
    with pytest.raises(ValueError, match="too many"):
        segment_speech_text("가" * 61, max_chars=30, max_segments=2)


def test_segmentation_packs_short_sentences_within_the_segment_budget():
    unit = (
        "비가 내린 뒤에는 공기 속 작은 물방울을 햇빛이 통과하면서 여러 색으로 나뉘어 보여. "
        "우리는 이것을 무지개라고 부르고, 해를 등진 채 비가 오는 쪽을 바라보면 더 잘 볼 수 있어. "
    )
    suffix = "마지막 검증 문구: 보라색 고래가 바다 위로 힘차게 뛰어올랐어."
    text = ""
    while len(text) + len(unit) + len(suffix) < 950:
        text += unit
    text += suffix

    segments = segment_speech_text(text, max_chars=120, max_segments=12)

    assert len(text) == 944
    assert len(segments) <= 12
    assert all(len(segment) <= 120 for segment in segments)
    assert compact_speech_text("".join(segments)) == compact_speech_text(text)


@pytest.mark.parametrize(
    "transcript",
    [
        "직접 말하기 어렵다면 그대로 말해도 돼.",
        "직접 말하기 어렵다면 그대로 말 해도 돼",
        "직접 말하기 어렵다면 거대로 말해도 돼.",
    ],
)
def test_verification_allows_minor_transcription_differences(transcript):
    result = verify_spoken_text(
        "직접 말하기 어렵다면 그대로 말해도 돼.",
        transcript,
        min_similarity=0.78,
        min_tail_similarity=0.72,
        tail_chars=18,
    )
    assert result.passed


@pytest.mark.parametrize(
    "transcript",
    [
        "직접 말하기 어렵다면",
        "직접 말하기 어렵다면 믿을 만한 어른에게 말해.",
        "",
    ],
)
def test_verification_rejects_missing_or_changed_ending(transcript):
    result = verify_spoken_text(
        "직접 말하기 어렵다면 그대로 말해도 돼.",
        transcript,
        min_similarity=0.78,
        min_tail_similarity=0.72,
        tail_chars=18,
    )
    assert not result.passed


@pytest.mark.parametrize(
    "updates",
    [
        {"tts_segment_max_chars": 29},
        {"tts_max_segments": 0},
        {"tts_verification_retries": 2},
        {"tts_verification_min_similarity": 0.49},
        {"tts_verification_tail_chars": 3},
    ],
)
def test_speech_verification_settings_are_bounded(updates):
    with pytest.raises(ValidationError):
        configuration(**updates)
