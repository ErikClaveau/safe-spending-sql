from pydantic import BaseModel, ConfigDict

from safe_spending.generator.events import Event
from safe_spending.generator.savings.savings_plan import SavingsPlan


class Savings(BaseModel):
    """A user's savings account, if they have one, and the transfers that go with it."""

    model_config = ConfigDict(frozen=True)

    plan: SavingsPlan | None
    events: tuple[Event, ...] = ()
