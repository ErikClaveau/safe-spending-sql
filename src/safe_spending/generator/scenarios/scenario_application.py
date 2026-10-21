from datetime import date

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.events import Event
from safe_spending.generator.schemas import ScenarioRow


class ScenarioApplication(BaseModel):
    """The result of applying every scenario assigned to one user."""

    model_config = ConfigDict(frozen=True)

    events: tuple[Event, ...]
    rows: tuple[ScenarioRow, ...] = ()
    signup_date: date | None = None
