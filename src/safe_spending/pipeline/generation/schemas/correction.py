from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.generation.schemas.correction_kind import CorrectionKind
from safe_spending.pipeline.generation.schemas.generator_response import GeneratorResponse


class Correction(BaseModel):
    """A previous answer and what was wrong with it, so the model can write the SQL again."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    response: GeneratorResponse = Field(description="What the model answered last time.")
    kind: CorrectionKind
    detail: str = Field(description="The validator's violations or the database's error, as they came.")
