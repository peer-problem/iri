"""Request-scoped, content-free completion measurements; never alters model requests."""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class CompletionMetrics:
    output_characters: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


active_metrics: ContextVar[CompletionMetrics | None] = ContextVar(
    "completion_metrics", default=None
)


def record_completion(payload: dict, text, finish_reason):
    metrics = active_metrics.get()
    if metrics is None:
        return
    # Missing/malformed usage must not invalidate an otherwise valid model response.
    if isinstance(text, str):
        metrics.output_characters = len(text.strip())
    if isinstance(finish_reason, str) and finish_reason in {
        "stop",
        "length",
        "content_filter",
        "tool_calls",
        "function_call",
    }:
        metrics.finish_reason = finish_reason
    usage = payload.get("usage")
    if isinstance(usage, dict):
        for name in ("prompt_tokens", "completion_tokens"):
            value = usage.get(name)
            if type(value) is int and value >= 0:
                setattr(metrics, name, value)
