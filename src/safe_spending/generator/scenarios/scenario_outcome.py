from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.generator.events import Event
from safe_spending.generator.schemas import ScenarioRow


class ScenarioOutcome(BaseModel):
    """What one injector returns: the user's new full event list and its `scenarios` row."""

    model_config = ConfigDict(frozen=True)

    events: tuple[Event, ...] = Field(description="The user's new full event list.")
    row: ScenarioRow = Field(description="The `scenarios` row, with the ground truth.")
    signup_date: date | None = Field(
        default=None, description="Only the scenarios that move the user's sign-up date."
    )
