import asyncio
from contextlib import asynccontextmanager

from pydantic import ValidationError

from api.app.answer_profile import ANSWER_PROFILE, support_response
from api.app.behavior import (
    GENERATION_V2,
    INPUT_V2,
    OUTPUT_V3,
    SUPPORT_GUIDANCE,
    SUPPORT_V3,
    BehaviorProfile,
    deterministic_input_decision,
)
from api.app.prompts import (
    generation_messages as build_generation_messages,
)
from api.app.prompts import input_guard_messages, output_guard_messages
from api.app.provider import ModelProvider, ModelUnavailable
from api.app.schemas import AgeBand, InputVerdict, OutputVerdict

FALLBACKS = ANSWER_PROFILE.fallbacks


class QueueFull(Exception):
    pass


class RequestGate:
    """A single-process admission limit. One running request plus bounded waiters."""

    def __init__(self, max_waiting: int):
        self.capacity = max_waiting + 1
        self.outstanding = 0
        self.lock = asyncio.Semaphore(1)

    @asynccontextmanager
    async def enter(self):
        # No await between testing and incrementing: atomic on this event loop.
        if self.outstanding >= self.capacity:
            raise QueueFull
        self.outstanding += 1
        try:
            async with self.lock:
                yield
        finally:
            self.outstanding -= 1


def generation_messages(
    age: AgeBand,
    history: list[dict[str, str]],
    profile: BehaviorProfile = "baseline",
    *,
    support: bool = False,
) -> list[dict[str, str]]:
    general = (
        GENERATION_V2
        if profile in {"full_v2", "kanana_v3", "kanana_v4", "kanana_v5"}
        else None
    )
    support_guidance = None
    if support:
        support_guidance = (
            (GENERATION_V2 + "\n" + SUPPORT_V3)
            if profile in {"kanana_v3", "kanana_v4", "kanana_v5"}
            else ((GENERATION_V2 + "\n") if profile == "full_v2" else "")
            + SUPPORT_GUIDANCE
        )
    return build_generation_messages(
        age,
        history,
        general_guidance=general,
        support_guidance=support_guidance,
        support=support,
    )


class ChatService:
    def __init__(self, provider: ModelProvider):
        self.provider = provider
        self.profile = provider.settings.behavior_profile

    async def respond(
        self,
        age: AgeBand,
        history: list[dict[str, str]],
        *,
        previous_action: str | None = None,
    ) -> tuple[str, str]:
        # The service receives server-constructed history, never arbitrary API roles.
        continuing_support = previous_action == "support" or any(
            message["role"] == "assistant"
            and message["content"] == FALLBACKS["support"]
            for message in history[:-1]
        )
        deterministic_support = False
        if self.profile in {"kanana_v4", "kanana_v5"}:
            deterministic = deterministic_input_decision(history)
            if deterministic == "allow":
                deterministic = None
            if deterministic == "support":
                if not continuing_support:
                    return support_response(history), "support"
                deterministic_support = True
            if deterministic is not None:
                if deterministic != "support":
                    return FALLBACKS[deterministic], deterministic
        input_messages = input_guard_messages(
            age,
            history,
            guidance=INPUT_V2 if self.profile != "baseline" else None,
            include_policy=False,
        )
        stage = "input_guard"
        try:
            verdict = (
                InputVerdict(decision="support")
                if deterministic_support
                else InputVerdict.model_validate_json(
                    await self.provider.complete(
                        input_messages,
                        max_tokens=80,
                        guard=True,
                        response_schema=InputVerdict.model_json_schema(),
                    )
                )
            )
            support = verdict.decision == "support" and (
                self.profile
                in {"support_v2", "full_v2", "kanana_v3", "kanana_v4", "kanana_v5"}
                or continuing_support
            )
            if (
                support
                and not continuing_support
                and self.profile in {"kanana_v3", "kanana_v4", "kanana_v5"}
            ):
                return support_response(history), "support"
            if verdict.decision != "allow" and not support:
                return FALLBACKS[verdict.decision], verdict.decision
            stage = "generation"
            candidate = await self.provider.complete(
                generation_messages(age, history, self.profile, support=support)
            )
            stage = "output_guard"
            output_messages = output_guard_messages(
                age,
                history,
                candidate,
                guidance=(
                    OUTPUT_V3
                    if self.profile in {"kanana_v3", "kanana_v4", "kanana_v5"}
                    else None
                ),
            )
            checked = OutputVerdict.model_validate_json(
                await self.provider.complete(
                    output_messages,
                    max_tokens=80,
                    guard=True,
                    response_schema=OutputVerdict.model_json_schema(),
                )
            )
            if checked.decision == "block":
                action = "support" if support else "redirect"
                fallback = "support_followup" if continuing_support else action
                return FALLBACKS[fallback], action
            return candidate, "support" if support else "answer"
        except ValidationError as exc:
            raise ModelUnavailable(
                "Invalid safety verdict", code="invalid_verdict", stage=stage
            ) from exc
        except ModelUnavailable as exc:
            exc.stage = stage
            raise
