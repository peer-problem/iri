"""Existing main profiles plus the opt-in V63 candidate; baseline stays the default."""

from dataclasses import dataclass, replace

from runpod.inference.behavior import (
    GENERATION_V2,
    INPUT_V2,
    INPUT_V3,
    OUTPUT_V3,
    SUPPORT_GUIDANCE,
    SUPPORT_V3,
    BehaviorProfile,
)
from runpod.inference.quality_v1 import (
    GENERAL_GUIDANCE as QUALITY_GENERAL_GUIDANCE,
)
from runpod.inference.quality_v1 import INPUT_GUIDANCE as QUALITY_INPUT_GUIDANCE
from runpod.inference.quality_v1 import OUTPUT_GUIDANCE as QUALITY_OUTPUT_GUIDANCE
from runpod.inference.quality_v1 import SUPPORT_GUIDANCE as QUALITY_SUPPORT_GUIDANCE
from runpod.inference.v63 import (
    GENERAL_GUIDANCE,
    INPUT_INTENT_CLARIFICATION,
    OUTPUT_CONTEXT_CLARIFICATION,
)


@dataclass(frozen=True)
class ProfileSpec:
    input_guidance: str | None = None
    input_policy: bool = True
    output_guidance: str | None = None
    general_guidance: str | None = None
    support_guidance: str = SUPPORT_GUIDANCE
    generate_support: bool = False
    recheck: bool = False


_BASELINE = ProfileSpec()
_INPUT_V2 = replace(_BASELINE, input_guidance=INPUT_V2, input_policy=False)
_SUPPORT_V2 = replace(_INPUT_V2, generate_support=True)
_INPUT_V3 = replace(_BASELINE, input_guidance=INPUT_V3)
_SUPPORT_V3 = replace(_INPUT_V3, generate_support=True, support_guidance=SUPPORT_V3)
_SAFETY_V3 = replace(_SUPPORT_V3, output_guidance=OUTPUT_V3)
_KANANA_V3 = replace(
    _BASELINE,
    input_guidance=INPUT_V2,
    input_policy=False,
    output_guidance=OUTPUT_V3,
    general_guidance=GENERATION_V2,
    support_guidance=GENERATION_V2 + "\n" + SUPPORT_V3,
    generate_support=True,
)
_KANANA_V4 = replace(_KANANA_V3)
_KANANA_V5 = replace(_KANANA_V4)

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
    "legacy_harm_v63": replace(
        _SAFETY_V3,
        input_guidance=INPUT_V3 + "\n" + INPUT_INTENT_CLARIFICATION,
        output_guidance=OUTPUT_V3 + "\n" + OUTPUT_CONTEXT_CLARIFICATION,
        general_guidance=GENERAL_GUIDANCE,
        recheck=True,
    ),
    "phase3_quality_v1": replace(
        _SAFETY_V3,
        input_guidance=QUALITY_INPUT_GUIDANCE,
        output_guidance=QUALITY_OUTPUT_GUIDANCE,
        general_guidance=QUALITY_GENERAL_GUIDANCE,
        support_guidance=QUALITY_SUPPORT_GUIDANCE,
    ),
    "kanana_v3": _KANANA_V3,
    "kanana_v4": _KANANA_V4,
    "kanana_v5": _KANANA_V5,
}
