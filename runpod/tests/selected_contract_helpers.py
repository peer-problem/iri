"""Mock response paths used to compare published code with frozen experiments."""

import itertools
import json
from types import SimpleNamespace

from runpod.inference.provider import ModelUnavailable
from runpod.inference.service import ChatService
from runpod.inference.trace import TurnTrace


def cases(profile):
    audit = profile in {"harm_audit_v50", "legacy_harm_v63"}
    for age, multi, decision, recheck, output in itertools.product(
        ["4-6", "7-10"],
        [False, True],
        ["allow", "redirect", "support", "clarify"],
        ["allow", "redirect", "support", "clarify"] if audit else ["allow"],
        ["allow", "block"],
    ):
        history = (
            [
                {"role": "user", "content": "처음 질문"},
                {"role": "assistant", "content": "앞선 답변"},
            ]
            if multi
            else []
        ) + [{"role": "user", "content": "이런 경우는 어떻게 해?"}]
        replies = [json.dumps({"decision": decision})]
        if audit and decision == "allow":
            replies.append(
                recheck if profile == "harm_audit_v50" else json.dumps({"decision": recheck})
            )
        replies += ["설명할게.", json.dumps({"decision": output})]
        yield {
            "name": f"{age}/{multi}/{decision}/{recheck}/{output}",
            "age": age,
            "history": history,
            "replies": replies,
        }
    for stage in ["input_guard", "input_recheck", "generation", "output_guard"]:
        if stage == "input_recheck" and not audit:
            continue
        for bad in [
            "",
            "nonsense",
            '{"decision":"allow","extra":true}',
            '{"decision":',
            "__upstream_error__",
        ]:
            replies = ['{"decision":"allow"}']
            if audit:
                replies += ["allow" if profile == "harm_audit_v50" else '{"decision":"allow"}']
            replies += ["설명할게.", '{"decision":"allow"}']
            index = {
                "input_guard": 0,
                "input_recheck": 1,
                "generation": 1 + audit,
                "output_guard": 2 + audit,
            }[stage]
            if stage == "generation" and bad != "__upstream_error__":
                continue
            replies[index] = bad
            yield {
                "name": f"error/{stage}/{bad}",
                "age": "7-10",
                "history": [{"role": "user", "content": "질문"}],
                "replies": replies,
            }


async def capture(profile, case):
    calls, replies = [], iter(case["replies"])

    class Provider:
        settings = SimpleNamespace(behavior_profile=profile)

        async def complete(self, messages, **kwargs):
            calls.append({"messages": messages, "kwargs": kwargs})
            reply = next(replies)
            if reply == "__upstream_error__":
                raise ModelUnavailable("Upstream unavailable", code="upstream_error")
            return reply

    trace = TurnTrace()
    try:
        result = await ChatService(Provider()).respond(case["age"], case["history"], trace=trace)
    except ModelUnavailable as exc:
        result = {"error": exc.code, "stage": exc.stage}
    snapshot = trace.snapshot()
    for item in snapshot["stages"].values():
        item.pop("seconds")
    return {"calls": calls, "result": result, "trace": snapshot}
