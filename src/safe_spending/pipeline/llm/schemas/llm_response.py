from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.llm.schemas.token_usage import TokenUsage


class LLMResponse(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    structured_output: str | None = Field(
        description="The structured output as JSON text, exactly as received. None if the model did not produce it."
    )
    text: str = Field(description="Any plain text the model wrote, for the trace.")
    model: str = Field(description="The model that served the request; differs from the requested one after a fallback.")
    stop_reason: str
    usage: TokenUsage
    cost_usd: Decimal | None = Field(description="None when the model has no known price.")
    latency_s: float
    request_id: str | None
