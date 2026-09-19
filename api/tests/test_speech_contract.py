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
        segment_speech_text("하나. 둘. 셋.", max_chars=30, max_segments=2)


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
