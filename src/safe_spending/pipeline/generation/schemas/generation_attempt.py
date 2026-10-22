from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from safe_spending.pipeline.generation.schemas.generator_response import GeneratorResponse
from safe_spending.pipeline.llm.schemas import LLMResponse


class GenerationAttempt(BaseModel):
    """One try at getting a valid response from the model; failed tries go to the trace too (ADR-006)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    raw: str = Field(description="The model's tool input exactly as received, JSON text. Empty if it made no call.")
    response: GeneratorResponse | None = Field(
        default=None,
        description="Set when `raw` validated."
    )
    error: str | None = Field(
        default=None,
        description="Set when it did not: why, for the trace and the retry."
    )
    llm: LLMResponse | None = Field(
        default=None,
        description="What the provider returned for this try: model, tokens, cost, latency."
    )

    @classmethod
    def from_raw(
            cls,
            raw: str,
            llm: LLMResponse | None = None
    ) -> Self:
        try:
            return cls(
                raw=raw,
                response=GeneratorResponse.model_validate_json(json_data=raw),
                llm=llm
            )
        except ValidationError as exc:
            return cls(
                raw=raw,
                error=str(exc),
                llm=llm
            )

    @classmethod
    def from_llm(
            cls,
            llm: LLMResponse
    ) -> Self:
        if llm.structured_output is None:
            return cls(
                raw="",
                error=f"the model did not call the tool (stop_reason={llm.stop_reason})",
                llm=llm
            )

        return cls.from_raw(
            raw=llm.structured_output,
            llm=llm
        )

    @property
    def valid(self) -> bool:
        return self.response is not None

    @model_validator(mode="after")
    def _exactly_one_outcome(self) -> Self:
        if (self.response is None) == (self.error is None):
            raise ValueError("an attempt has either a response or an error")

        return self
