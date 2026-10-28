from datetime import date

from safe_spending.pipeline.verification.enums import DatePart


class DateParts:
    """The days, months and years of the dates a result, a query or the calendar contains."""

    def __init__(self) -> None:
        self.days: set[int] = set()
        self.months: set[int] = set()
        self.years: set[int] = set()

    def add(self, year: int, month: int, day: int) -> None:
        self.years.add(year)
        self.months.add(month)
        self.days.add(day)

    def add_date(self, value: date) -> None:
        self.add(value.year, value.month, value.day)

    def has(self, part: DatePart, value: int) -> bool:
        return value in {DatePart.DAY: self.days, DatePart.MONTH: self.months, DatePart.YEAR: self.years}[part]
