from pydantic import BaseModel, ConfigDict, Field

from safe_spending.evals.golden import Behavior, Category, Difficulty, Split


class SampleMetadata(BaseModel):
    """What a sample carries besides the question: who asks, how it is graded and the reference answer."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    user_id: int = Field(description="The user the question is asked as.")
    category: Category
    split: Split = Field(description="Dev, or the held-out test part of the golden set.")
    difficulty: Difficulty
    behavior: Behavior = Field(description="What the assistant is expected to do.")
    ordered: bool = Field(description="Whether row order matters when comparing results.")
    expected: dict | None = Field(default=None, description="Reference result (ResultTable JSON); none unless it answers.")
