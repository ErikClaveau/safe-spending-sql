from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.llm.schemas.llm_message import LLMMessage


class LLMRequest(BaseModel):
    """What the pipeline asks of a model, independent of the provider (ADR-004, ADR-006)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    system: str
    messages: tuple[LLMMessage, ...] = Field(min_length=1)
    output_name: str = Field(description="Name of the structured output, e.g. the tool the model must call.")
    output_description: str
    output_schema: dict = Field(description="JSON schema of the structured output (a Pydantic `model_json_schema`).")
