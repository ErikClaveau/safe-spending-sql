from pydantic import BaseModel, ConfigDict

from safe_spending.pipeline.llm.schemas.llm_role import LLMRole


class LLMMessage(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    role: LLMRole
    content: str
