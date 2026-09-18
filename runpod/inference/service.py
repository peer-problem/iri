from contextlib import nullcontext

from pydantic import ValidationError

from runpod.inference.messages import POLICY as POLICY
from runpod.inference.messages import generation_messages as generation_messages
from runpod.inference.messages import input_guard_messages, input_recheck_messages
from runpod.inference.messages import output_guard_messages as output_guard_messages
from runpod.inference.profiles import PROFILES
from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.schemas import AgeBand, InputVerdict, OutputVerdict
from runpod.inference.trace import StageTrace, TurnTrace

FALLBACKS = {
    "redirect": "다칠 수 있는 내용은 안내하기 어려워. 안전한 방법을 함께 찾아보자. 누군가 너를 괴롭히거나 불편하게 한다면 믿을 수 있는 선생님이나 어른에게 도움을 요청해 줘.",
    "support": "말해 줘서 고마워. 혼자 해결하지 않아도 돼. 지금 위험하다면 안전한 곳으로 가서 믿을 수 있는 선생님이나 어른에게 바로 도움을 요청해 줘.",
    "clarify": "무엇이 궁금한지 조금 더 자세히 말해 줄래?",
    "unavailable": "지금은 답변을 준비하기 어려워. 잠시 뒤에 다시 물어봐 줘.",
}


class ChatService:
    def __init__(self, provider: ModelProvider):
        self.provider = provider
        self.profile = provider.settings.behavior_profile
        self.spec = PROFILES[self.profile]

    async def respond(
        self, age: AgeBand, history: list[dict[str, str]], *, trace: TurnTrace | None = None
    ) -> tuple[str, str]:
        # The service receives server-constructed history, never arbitrary API roles.
        input_messages = input_guard_messages(age, history, self.profile)
        stage = "input_guard"
        try:
            with trace.measure(stage) if trace else nullcontext():
                verdict = InputVerdict.model_validate_json(
                    await self.provider.complete(
                        input_messages,
                        max_tokens=80,
                        guard=True,
                        response_schema=InputVerdict.model_json_schema(),
                    )
                )
                if trace:
                    trace.stages[stage].decision = verdict.decision
            if self.spec.recheck and verdict.decision == "allow":
                stage = "input_recheck"
                if trace:
                    trace.stages[stage] = StageTrace()
                messages = input_recheck_messages(age, input_messages, self.spec.recheck)
                with trace.measure(stage) if trace else nullcontext():
                    recheck = await self._recheck(messages)
                    if trace:
                        trace.stages[stage].decision = recheck.decision
                    # The recheck can veto harmful execution requests, but cannot
                    # silently reroute allow to support or clarify.
                    if recheck.decision == "redirect":
                        verdict = recheck
            support = verdict.decision == "support" and self.spec.generate_support
            if verdict.decision != "allow" and not support:
                if trace:
                    trace.finish(verdict.decision, fallback=True)
                return FALLBACKS[verdict.decision], verdict.decision
            stage = "generation"
            with trace.measure(stage) if trace else nullcontext():
                candidate = await self.provider.complete(
                    generation_messages(age, history, self.profile, support=support)
                )
            stage = "output_guard"
            output_messages = output_guard_messages(age, history, candidate, self.profile)
            with trace.measure(stage) if trace else nullcontext():
                checked = OutputVerdict.model_validate_json(
                    await self.provider.complete(
                        output_messages,
                        max_tokens=80,
                        guard=True,
                        response_schema=OutputVerdict.model_json_schema(),
                    )
                )
                if trace:
                    trace.stages[stage].decision = checked.decision
            if checked.decision == "block":
                action = "support" if support else "redirect"
                if trace:
                    trace.finish(action, fallback=True)
                return FALLBACKS[action], action
            if trace:
                trace.finish("support" if support else "answer", fallback=False)
            return candidate, "support" if support else "answer"
        except ValidationError as exc:
            raise ModelUnavailable(
                "Invalid safety verdict", code="invalid_verdict", stage=stage
            ) from exc
        except ModelUnavailable as exc:
            exc.stage = stage
            raise

    async def _recheck(self, messages: list[dict[str, str]]) -> InputVerdict:
        if self.spec.recheck == "legacy_label":
            # V50 only: historical non-JSON protocol, ineligible for adoption.
            raw = await self.provider.complete(messages, max_tokens=80, guard=True)
            return InputVerdict(decision=raw.strip())
        return InputVerdict.model_validate_json(
            await self.provider.complete(
                messages,
                max_tokens=80,
                guard=True,
                response_schema=InputVerdict.model_json_schema(),
            )
        )
