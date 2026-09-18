"""Opt-in evaluation diagnostics; never store prompts, answers or upstream bodies."""

import asyncio
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

from pydantic import ValidationError

from runpod.inference.provider import ModelUnavailable
from runpod.inference.telemetry import CompletionMetrics, active_metrics


@dataclass
class StageTrace(CompletionMetrics):
    status: str = "not_run"
    seconds: float | None = None
    decision: str | None = None
    error_code: str | None = None


@dataclass
class TurnTrace:
    stages: dict[str, StageTrace] = field(
        default_factory=lambda: {
            name: StageTrace() for name in ("input_guard", "generation", "output_guard")
        }
    )
    final_action: str | None = None
    fallback_used: bool | None = None

    @contextmanager
    def measure(self, name: str):
        stage = self.stages[name]
        stage.status = "running"
        started = time.monotonic()
        token = active_metrics.set(stage)
        try:
            yield stage
        except BaseException as exc:
            stage.status = "error"
            if isinstance(exc, ModelUnavailable):
                stage.error_code = exc.code
            elif isinstance(exc, ValidationError):
                stage.error_code = "invalid_verdict"
            elif isinstance(exc, TimeoutError):
                stage.error_code = "timeout"
            elif isinstance(exc, asyncio.CancelledError):
                # An outer asyncio timeout also arrives as cancellation here.
                stage.status = "interrupted"
                stage.error_code = "cancelled"
            else:
                stage.error_code = "unexpected_error"
            raise
        else:
            stage.status = "completed"
        finally:
            active_metrics.reset(token)
            stage.seconds = round(time.monotonic() - started, 6)

    def finish(self, action: str | None, *, fallback: bool):
        self.final_action = action
        self.fallback_used = fallback

    def snapshot(self) -> dict:
        return asdict(self)
