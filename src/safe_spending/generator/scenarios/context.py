from datetime import date
from functools import cached_property

import numpy as np
from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.dates import months
from safe_spending.generator.events import Event
from safe_spending.generator.fx import FxSeries
from safe_spending.generator.profile import Profile


class ScenarioContext(BaseModel):
    """What an injector receives: the user's baseline events and the `scenarios` random stream."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    config: GeneratorConfig
    catalog: Catalog
    fx: FxSeries
    profile: Profile
    events: tuple[Event, ...]
    rng: np.random.Generator
    end: date
    scenario_id: str

    @cached_property
    def timeline(self) -> list[tuple[int, int]]:
        """(year, month) of every month of the period, the last one possibly partial."""
        return list(months(self.config.period_start, self.end))
