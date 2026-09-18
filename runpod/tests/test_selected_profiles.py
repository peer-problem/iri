"""Golden contracts were captured from each version's original source ZIP, not this implementation."""

import hashlib
import json
from pathlib import Path
from typing import get_args

import pytest

from runpod.inference.behavior import BehaviorProfile
from runpod.inference.profiles import PROFILES
from runpod.inference.selected_profiles import SELECTED_PROFILES
from runpod.inference.service import generation_messages
from runpod.settings import Settings
from runpod.tests.selected_contract_helpers import capture, cases


def test_every_public_profile_has_an_explicit_configuration():
    assert set(PROFILES) == set(get_args(BehaviorProfile))


@pytest.mark.parametrize("profile", sorted(SELECTED_PROFILES))
async def test_frozen_request_routing_and_error_contract(profile):
    expected = json.loads((Path(__file__).parent / "fixtures" / f"{profile}.json").read_text())
    observed = {}
    for case in cases(profile):
        result = await capture(profile, case)
        observed[case["name"]] = hashlib.sha256(
            json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
    assert observed == expected


@pytest.mark.parametrize("profile", sorted(SELECTED_PROFILES))
@pytest.mark.parametrize("support", [False, True])
def test_selected_profiles_preserve_v10_generation_and_opt_in(profile, support):
    assert Settings(_env_file=None).behavior_profile == "baseline"
    assert Settings(_env_file=None, behavior_profile=profile).behavior_profile == profile
    history = [{"role": "user", "content": "오늘 기분이 어때?"}]
    assert generation_messages("4-6", history, profile, support=support) == generation_messages(
        "4-6", history, "trim_v10", support=support
    )
