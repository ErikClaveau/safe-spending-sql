"""The `Clock` port: nothing in the pipeline reads the system date directly (ADR-008).

Evals and the demo use `FixedClock` with the frozen "today" of the dataset (2026-09-15).
"""

from datetime import date
from typing import Protocol


class Clock(Protocol):
    def today(self) -> date: ...
