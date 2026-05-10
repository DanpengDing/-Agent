from typing import List, Optional

from pydantic import BaseModel, Field


class StructuredAgentOutput(BaseModel):
    intent: str = Field(default="general")
    answer: str = Field(default="")
    references: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None
