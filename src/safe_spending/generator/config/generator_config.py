from datetime import date

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config.archetype import Archetype


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

    def split_of(
            self,
            user_id: int
    ) -> str:
        for name, (low, high) in self.splits.items():
            if low <= user_id <= high:
                return name
        raise ValueError(f"user_id {user_id} is outside every split")
