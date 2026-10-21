from datetime import date
from typing import NamedTuple

import numpy as np

from safe_spending.generator.dates import daterange


class Calendar(NamedTuple):
    """The simulated days and, per day, the weekday and month index used to scale the rate."""

    days: list[date]
    weekdays: np.ndarray
    month_index: np.ndarray

    @classmethod
    def between(
            cls,
            start: date,
            end: date
    ) -> "Calendar":
        days = daterange(start, end)

        return cls(
            days=days,
            weekdays=np.array([d.weekday() for d in days]),
            month_index=np.array([d.month - 1 for d in days])
        )
