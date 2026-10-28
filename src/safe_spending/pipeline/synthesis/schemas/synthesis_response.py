from pydantic import BaseModel, ConfigDict, Field, field_validator


class SynthesisResponse(BaseModel):
    """The structured answer of the synthesizer: the contract of the `AnswerSynthesizer` port."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    answer: str = Field(description="The answer to the user's question, in Spanish, from the query result only.")

    @field_validator("answer")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the answer is empty")

        return value
