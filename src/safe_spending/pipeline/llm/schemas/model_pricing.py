from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.llm.schemas.token_usage import TokenUsage

_MILLION = Decimal(1_000_000)


class ModelPricing(BaseModel):
    """USD per million tokens."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal = Field(description="Five-minute cache write.")

    def cost(
            self,
            usage: TokenUsage
    ) -> Decimal:
        return (
                usage.input_tokens * self.input
                + usage.output_tokens * self.output
                + usage.cache_read_tokens * self.cache_read
                + usage.cache_write_tokens * self.cache_write
        ) / _MILLION
