import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.evals.golden.enums import FORCED_BEHAVIOR, Behavior, Category, Difficulty

ID_PATTERN = re.compile(r"^GS-\d{3}$")


class GoldenQuestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Stable identifier, GS-001 and up. Never reused.")
    question: str = Field(description="The question as the user writes it, in Spanish.")
    user_id: int = Field(description="The evaluation user the question is asked as (1-15).")
    category: Category = Field(description="Question category.")
    difficulty: Difficulty = Field(description="How hard the question is for the assistant.")
    behavior: Behavior = Field(description="What the assistant is expected to do.")
    reference_sql: str | None = Field(
        default=None,
        description="SQL over the semantic views that yields the expected answer, or the evidence for no_data.",
    )
    ordered: bool = Field(
        default=False,
        description="True when the order of the rows is part of the answer."
    )
    scenario_id: str | None = Field(
        default=None,
        description="The scripted scenario the question is anchored to, whose params give the truth independently.",
    )
    notes: str | None = Field(
        default=None,
        description="Why the question is here or what it checks."
    )

    @model_validator(mode="after")
    def _is_coherent(self) -> "GoldenQuestion":
        if not ID_PATTERN.match(self.id):
            raise ValueError(f"{self.id}: the id must look like GS-001")
        expected = FORCED_BEHAVIOR.get(self.category, Behavior.ANSWER)
        if self.behavior != expected:
            raise ValueError(f"{self.id}: category {self.category} expects behavior {expected}, not {self.behavior}")
        needs_sql = self.behavior in (Behavior.ANSWER, Behavior.NO_DATA)
        if needs_sql and not (self.reference_sql or "").strip():
            raise ValueError(f"{self.id}: behavior {self.behavior} needs a reference_sql")
        if not needs_sql and self.reference_sql:
            raise ValueError(f"{self.id}: behavior {self.behavior} has no SQL")
        if self.ordered and self.reference_sql and "order by" not in self.reference_sql.lower():
            raise ValueError(f"{self.id}: ordered: true needs an ORDER BY in the reference SQL")
        return self
