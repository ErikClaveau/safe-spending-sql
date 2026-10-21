from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.evals.golden.question import GoldenQuestion

GOLDEN_DIR = Path(__file__).parents[4] / "evals" / "golden"
GOLDEN_FILE = GOLDEN_DIR / "golden_v0.yaml"
EXPECTED_FILE = GOLDEN_DIR / "expected_v0.json"


class GoldenSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str = Field(description="Version of the dataset the expected answers belong to.")
    reference_date: date = Field(description="The frozen 'today' of the dataset: what 'este año' means.")
    questions: tuple[GoldenQuestion, ...] = Field(description="The questions, in id order.")

    @model_validator(mode="after")
    def _ids_are_unique_and_in_order(self) -> "GoldenSet":
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate question ids")
        if ids != sorted(ids):
            raise ValueError("the questions must be listed in id order")
        return self

    def question_by_id(self, question_id: str) -> GoldenQuestion:
        return next(q for q in self.questions if q.id == question_id)

    @property
    def answerable(self) -> tuple[GoldenQuestion, ...]:
        """The questions that have a reference SQL, i.e. an expected result to compare with."""
        return tuple(q for q in self.questions if q.reference_sql)


def load_golden_set(path: Path = GOLDEN_FILE) -> GoldenSet:
    return GoldenSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
