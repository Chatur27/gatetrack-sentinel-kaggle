from pydantic import BaseModel, ConfigDict, Field


class ReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reviewer: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=3, max_length=500)
