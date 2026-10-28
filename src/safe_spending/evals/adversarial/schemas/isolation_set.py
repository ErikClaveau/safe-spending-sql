from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.evals.adversarial.schemas.isolation_question import IsolationQuestion


class IsolationSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str = Field(description="Version of the dataset the expected results belong to.")
    reference_date: date = Field(description="The frozen 'today' of the dataset.")
    questions: tuple[IsolationQuestion, ...] = Field(description="The questions, in id order.")

    @model_validator(mode="after")
    def _ids_are_unique_and_in_order(self) -> "IsolationSet":
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate question ids")
        if ids != sorted(ids):
            raise ValueError("the questions must be listed in id order")
        return self
