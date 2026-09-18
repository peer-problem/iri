"""V63 contracts captured from published 771ccc3, never from the new implementation."""

import hashlib
import json
from pathlib import Path
from typing import get_args

import pytest

from runpod.inference.behavior import BehaviorProfile
from runpod.inference.profiles import PROFILES
from runpod.settings import Settings
from runpod.tests.v63_contracts import capture, cases

EXPECTED = json.loads((Path(__file__).parent / "fixtures/v63_requests.json").read_text())
TRACED = json.loads((Path(__file__).parent / "fixtures/legacy_harm_v63.json").read_text())


@pytest.mark.parametrize("case", list(cases("legacy_harm_v63")), ids=lambda case: case["name"])
@pytest.mark.parametrize("include_trace", [False, True])
async def test_published_v63_request_result_and_error_contract(case, include_trace):
    result = await capture("legacy_harm_v63", case, include_trace=include_trace)
    digest = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    assert digest == (TRACED if include_trace else EXPECTED)[case["name"]]


def test_v63_is_opt_in_and_every_public_profile_has_a_configuration():
    assert Settings(_env_file=None).behavior_profile == "baseline"
    assert (
        Settings(_env_file=None, behavior_profile="legacy_harm_v63").behavior_profile
        == "legacy_harm_v63"
    )
    assert set(PROFILES) == set(get_args(BehaviorProfile))
