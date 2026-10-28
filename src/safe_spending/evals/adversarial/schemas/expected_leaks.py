from pydantic import BaseModel, ConfigDict, Field

from safe_spending.evals.golden import ResultTable


class ExpectedLeaks(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_version: str
    config_hash: str
    victim: dict[str, dict] = Field(description="Result of each reference SQL as the victim.")
    own: dict[str, dict] = Field(description="Result of the same SQL as the asker.")

    def victim_table(self, question_id: str) -> ResultTable:
        return ResultTable.from_json(self.victim[question_id])

    def own_table(self, question_id: str) -> ResultTable:
        return ResultTable.from_json(self.own[question_id])
