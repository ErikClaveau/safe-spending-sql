from pydantic import BaseModel, ConfigDict, Field


class TokenUsage(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    input_tokens: int = Field(description="Uncached input tokens.")
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
