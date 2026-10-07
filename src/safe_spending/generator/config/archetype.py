from pydantic import BaseModel, ConfigDict


class Archetype(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    weight: float
    annual_net_income_eur: tuple[float, float]
    rent_share: tuple[float, float]
    pay_day: tuple[int, int]
    rent_day: tuple[int, int]
    subscriptions: tuple[int, int]
    category_budget_share: dict[str, float]
