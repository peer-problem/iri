"""Explicit routing for reproducible behavior profiles; baseline remains the default."""

from dataclasses import dataclass, replace
from typing import Literal

from runpod.inference.behavior import (
    GENERATION_V2,
    INPUT_V2,
    INPUT_V3,
    OUTPUT_V3,
    SUPPORT_GUIDANCE,
    SUPPORT_V3,
    TRIM_V10,
    BehaviorProfile,
)
from runpod.inference.selected_profiles import (
    INPUT_INTENT_CLARIFICATION,
    OUTPUT_CONTEXT_CLARIFICATION,
)

RecheckFormat = Literal["json", "legacy_label"]


@dataclass(frozen=True)
class ProfileSpec:
    input_guidance: str | None = None
    input_policy: bool = True
    output_guidance: str | None = None
    general_guidance: str | None = None
    support_guidance: str = SUPPORT_GUIDANCE
    generate_support: bool = False
    primary_examples: bool = False
    recheck: RecheckFormat | None = None


_BASELINE = ProfileSpec()
_INPUT_V2 = replace(_BASELINE, input_guidance=INPUT_V2, input_policy=False)
_SUPPORT_V2 = replace(_INPUT_V2, generate_support=True)
_INPUT_V3 = replace(_BASELINE, input_guidance=INPUT_V3)
_SUPPORT_V3 = replace(_INPUT_V3, generate_support=True, support_guidance=SUPPORT_V3)
_SAFETY_V3 = replace(_SUPPORT_V3, output_guidance=OUTPUT_V3)
_TRIM_V10 = replace(_SAFETY_V3, general_guidance=TRIM_V10)
_OUTPUT_V16 = replace(
    _TRIM_V10,
    input_guidance=INPUT_V3 + "\n" + INPUT_INTENT_CLARIFICATION,
    output_guidance=OUTPUT_V3 + "\n" + OUTPUT_CONTEXT_CLARIFICATION,
)

# Public CLI names identify frozen experiments and remain backward compatible.
# V63 = V16 messages + a JSON harm recheck. Only redirect overrides the first verdict.
PROFILES: dict[BehaviorProfile, ProfileSpec] = {
    "baseline": _BASELINE,
    "input_v2": _INPUT_V2,
    "support_v2": _SUPPORT_V2,
    "full_v2": replace(
        _SUPPORT_V2,
        general_guidance=GENERATION_V2,
        support_guidance=GENERATION_V2 + "\n" + SUPPORT_GUIDANCE,
    ),
    "input_v3": _INPUT_V3,
    "support_v3": _SUPPORT_V3,
    "safety_v3": _SAFETY_V3,
    "trim_v10": _TRIM_V10,
    "output_v16": _OUTPUT_V16,
    "boundary_v25": replace(_OUTPUT_V16, primary_examples=True),
    "harm_audit_v50": replace(_OUTPUT_V16, recheck="legacy_label"),
    "legacy_harm_v63": replace(_OUTPUT_V16, recheck="json"),
}
