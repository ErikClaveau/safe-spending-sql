from pydantic import BaseModel, ConfigDict, Field

from safe_spending.evals.golden.results import ResultTable


class ExpectedAnswers(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_version: str = Field(description="Dataset version the answers were computed on.")
    config_hash: str = Field(description="Hash of the generator configuration, so a data change is visible.")
    answers: dict[str, dict] = Field(description="Result of each answerable question: columns and rows.")

    def table(self, question_id: str) -> ResultTable:
        return ResultTable.from_json(self.answers[question_id])
