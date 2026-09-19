"""Message construction, separate from model calls and safety routing.

Prompt text, JSON key order and example order are part of the frozen contracts.
"""

from api.app.prompts import POLICY as POLICY
from api.app.prompts import generation_messages as build_generation_messages
from api.app.prompts import input_guard_messages as build_input_guard_messages
from api.app.prompts import output_guard_messages as build_output_guard_messages
from runpod.inference.behavior import BehaviorProfile
from runpod.inference.profiles import PROFILES
from runpod.inference.schemas import AgeBand
from runpod.inference.v63 import input_example_messages


def generation_messages(
    age: AgeBand,
    history: list[dict[str, str]],
    profile: BehaviorProfile = "baseline",
    *,
    support: bool = False,
) -> list[dict[str, str]]:
    spec = PROFILES[profile]
    return build_generation_messages(
        age,
        history,
        general_guidance=spec.general_guidance,
        support_guidance=spec.support_guidance,
        support=support,
        include_answer_profile=profile in {"kanana_v3", "kanana_v4", "kanana_v5"},
    )


def input_guard_messages(
    age: AgeBand, history: list[dict[str, str]], profile: BehaviorProfile
) -> list[dict[str, str]]:
    spec = PROFILES[profile]
    return build_input_guard_messages(
        age,
        history,
        guidance=spec.input_guidance,
        include_policy=spec.input_policy,
    )


def input_recheck_messages(age: AgeBand, primary: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        dict(primary[0]),
        *input_example_messages(age),
        dict(primary[-1]),
    ]


def output_guard_messages(
    age: AgeBand,
    history: list[dict[str, str]],
    candidate: str,
    profile: BehaviorProfile = "baseline",
) -> list[dict[str, str]]:
    spec = PROFILES[profile]
    return build_output_guard_messages(
        age,
        history,
        candidate,
        guidance=spec.output_guidance,
    )
