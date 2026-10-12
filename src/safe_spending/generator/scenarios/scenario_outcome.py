from datetime import date

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.events import Event
from safe_spending.generator.schemas import ScenarioRow


class ScenarioOutcome(BaseModel):
    """What one injector returns: the user's new full event list and its `scenarios` row."""

    model_config = ConfigDict(frozen=True)

    events: tuple[Event, ...]
    row: ScenarioRow
    signup_date: date | None = None  # only the scenarios that move the user's sign-up date
