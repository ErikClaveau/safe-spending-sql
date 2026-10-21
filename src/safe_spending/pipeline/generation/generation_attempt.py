from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from safe_spending.pipeline.generation.generator_response import GeneratorResponse


class GenerationAttempt(BaseModel):
    """One try at getting a valid response from the model; failed tries go to the trace too (ADR-006)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    raw: str = Field(description="The model's tool input exactly as received, JSON text.")
    response: GeneratorResponse | None = Field(
        default=None,
        description="Set when `raw` validated."
    )
    error: str | None = Field(
        default=None,
        description="Set when it did not: why, for the trace and the retry."
    )

    @classmethod
    def from_raw(
            cls,
            raw: str
    ) -> Self:
        try:
            return cls(
                raw=raw,
                response=GeneratorResponse.model_validate_json(json_data=raw)
            )
        except ValidationError as exc:
            return cls(
                raw=raw,
                error=str(exc)
            )

    @property
    def valid(self) -> bool:
        return self.response is not None

    @model_validator(mode="after")
    def _exactly_one_outcome(self) -> Self:
        if (self.response is None) == (self.error is None):
            raise ValueError("an attempt has either a response or an error")

        return self
