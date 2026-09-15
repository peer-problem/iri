from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgeBand = Literal["4-6", "7-10"]
Action = Literal["answer", "redirect", "support", "clarify", "unavailable"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    age_band: AgeBand
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    action: Action
    request_id: UUID


class InputVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["allow", "redirect", "support", "clarify"]


class OutputVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["allow", "block"]
