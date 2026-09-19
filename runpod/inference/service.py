from contextlib import nullcontext

from pydantic import ValidationError

from runpod.inference.behavior import deterministic_input_decision
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


def support_response(history: list[dict[str, str]]) -> str:
    text = next(
        (message["content"] for message in reversed(history) if message["role"] == "user"), ""
    )
    if any(word in text for word in ("비밀번호", "계정", "로그인")):
        return (
            "당황했겠다. 이전 비밀번호나 새 비밀번호를 채팅에 쓰지 말고, 믿을 수 있는 "
            "어른과 함께 그 계정의 비밀번호를 바꾸고 로그아웃 같은 보호 조치를 해 줘."
        )
    if "사진" in text and any(word in text for word in ("보내", "달라", "요구")):
        return (
            "당황스럽고 불편했겠다. 사진이나 개인정보를 더 보내지 말고 대화를 멈춘 뒤, "
            "내용을 지우지 말고 믿을 수 있는 어른에게 보여 주며 도움을 요청해 줘."
        )
    if any(word in text for word in ("길을 잃", "길 잃", "보호자를 못 찾", "엄마를 못 찾")):
        return (
            "무섭겠구나. 혼자 돌아다니거나 낯선 사람을 따라가지 말고, 가까운 가게 직원이나 "
            "경찰관, 안전요원에게 보호자를 찾는 도움을 요청해 줘. 주소를 여기 적지 않아도 돼."
        )
    if any(word in text for word in ("없어졌으면", "죽고 싶", "사라지고 싶", "자해")):
        return (
            "많이 힘들었구나. 지금 혼자 있지 말고 바로 가까운 믿을 수 있는 어른에게 이 말을 "
            "보여 주거나 말해 줘. 지금 다칠 것 같다면 안전한 곳으로 가서 현지 긴급 도움을 요청해 줘."
        )
    if any(word in text for word in ("때려", "맞아", "아프게", "괴롭혀", "해쳐")):
        return (
            "많이 무섭고 아팠겠다. 네 잘못이 아니야. 보복하거나 혼자 참지 말고, 지금 위험하면 "
            "안전한 곳으로 가서 가해자로 지목되지 않은 믿을 수 있는 선생님이나 안전요원에게 바로 알려 줘."
        )
    if any(word in text for word in ("무서워", "두려워", "겁나")):
        return (
            "무서웠구나. 화면이나 활동을 멈추고 쉬어도 돼. 혼자 견디지 말고 가까운 믿을 수 "
            "있는 어른에게 말해 줘."
        )
    return FALLBACKS["support"]


class ChatService:
    def __init__(self, provider: ModelProvider):
        self.provider = provider
        self.profile = provider.settings.behavior_profile
        self.spec = PROFILES[self.profile]

    async def respond(
        self, age: AgeBand, history: list[dict[str, str]], *, trace: TurnTrace | None = None
    ) -> tuple[str, str]:
        # The service receives server-constructed history, never arbitrary API roles.
        if self.profile in {"kanana_v4", "kanana_v5"}:
            deterministic = deterministic_input_decision(history)
            if deterministic == "allow":
                deterministic = None
            if deterministic is not None:
                if trace:
                    trace.finish(deterministic, fallback=True)
                if deterministic == "support":
                    return support_response(history), "support"
                return FALLBACKS[deterministic], deterministic
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
                messages = input_recheck_messages(age, input_messages)
                with trace.measure(stage) if trace else nullcontext():
                    recheck = await self._recheck(messages)
                    if trace:
                        trace.stages[stage].decision = recheck.decision
                    # The recheck can veto harmful execution requests, but cannot
                    # silently reroute allow to support or clarify.
                    if recheck.decision == "redirect":
                        verdict = recheck
            support = verdict.decision == "support" and self.spec.generate_support
            if support and self.profile in {"kanana_v3", "kanana_v4", "kanana_v5"}:
                if trace:
                    trace.finish("support", fallback=True)
                return support_response(history), "support"
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
        return InputVerdict.model_validate_json(
            await self.provider.complete(
                messages,
                max_tokens=80,
                guard=True,
                response_schema=InputVerdict.model_json_schema(),
            )
        )
