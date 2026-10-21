from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Merchant
from safe_spending.generator.profile.subscription import Subscription
from safe_spending.generator.profile.utility import Utility


class Profile(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int
    archetype: str
    name: str
    city: str
    employer: str
    landlord: str
    iban: str
    card_prefix: str
    annual_net_cents: int
    monthly_income_cents: int
    pay_day: int
    rent_cents: int
    rent_day: int
    utilities: tuple[Utility, ...]
    subscriptions: tuple[Subscription, ...]
    habitual: dict[str, tuple[tuple[Merchant, float], ...]]
    budget_noise: float
