"""Calendar helpers. Business days are Monday to Friday; Spanish public holidays are
added in a later slice behind `is_business_day`."""

from calendar import monthrange
from datetime import date, timedelta
from typing import Iterator

MONTHS_PER_YEAR = 12


def is_business_day(day: date) -> bool:
    return day.weekday() < 5


def next_business_day(day: date) -> date:
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def daterange(
        start: date,
        end: date
) -> list[date]:
    """Every date from start to end, both included."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def months(
        start: date,
        end: date
) -> Iterator[tuple[int, int]]:
    """(year, month) for every month touched by [start, end]."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > MONTHS_PER_YEAR:
            year, month = year + 1, 1


def day_in_month(
        year: int,
        month: int,
        day: int
) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))
