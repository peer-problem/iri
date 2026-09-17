from typing import Literal

from pydantic import BaseModel, ConfigDict

AgeBand = Literal["4-6", "7-10"]


class InputVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["allow", "redirect", "support", "clarify"]


class OutputVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["allow", "block"]
