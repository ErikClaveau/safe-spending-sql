
from datetime import date

from .clock import Clock


class SystemClock(Clock):
    def today(self) -> date:
        return date.today()
