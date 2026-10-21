from datetime import date

from .clock import Clock


class FixedClock(Clock):
    def __init__(
            self,
            today: date
    ) -> None:
        self._today = today

    def today(self) -> date:
        return self._today