from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator

from safe_spending.generator.config.archetype import Archetype
from safe_spending.generator.config.scenario_assignment import ScenarioAssignment

FUNCTIONAL_SPLIT = "eval_functional"


class GeneratorConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_version: str
    seed: int
    reference_date: date
    period_start: date
    n_users: int
    splits: dict[str, tuple[int, int]]
    statement_max_length: int
    cities: dict[str, float]
    weekday_weights: list[float]
    card_delay_weights: list[float]
    seasonality: dict[str, list[float]]
    archetypes: dict[str, Archetype]
    scenarios: tuple[ScenarioAssignment, ...] = ()

    @model_validator(mode="after")
    def _scenarios_belong_to_functional_users(self) -> "GeneratorConfig":
        low, high = self.splits[FUNCTIONAL_SPLIT]
        for assignment in self.scenarios:
            if not low <= assignment.user_id <= high:
                raise ValueError(
                    f"scenario {assignment.type} is assigned to user {assignment.user_id}, "
                    f"outside the {FUNCTIONAL_SPLIT} split {low}-{high}"
                )
        if len(set(self.scenarios)) != len(self.scenarios):
            raise ValueError("a scenario is assigned twice to the same user")
        return self

    def split_of(
            self,
            user_id: int
    ) -> str:
        for name, (low, high) in self.splits.items():
            if low <= user_id <= high:
                return name
        raise ValueError(f"user_id {user_id} is outside every split")

    def scenarios_of(
            self,
            user_id: int
    ) -> list[ScenarioAssignment]:
        return [a for a in self.scenarios if a.user_id == user_id]
