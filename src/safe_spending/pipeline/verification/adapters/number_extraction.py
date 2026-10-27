"""Finding numbers in Spanish text and in result cells, as `Decimal`.

Text is written as `1.234,56`; a lone `1.234` is ambiguous (thousands or decimals), so a token yields every
reading it can have and counts as traced if any of them is. Signs are dropped: "has gastado 12,50 €" is the
`-12.50` of a result. A digit run glued to letters (`CNR0168Q3W`) is part of a code, not a number.

Dates are kept apart. If the day, month and year of a date cell counted as plain numbers, "son 4 movimientos"
would pass whenever a row falls on the 4th. So a date in the answer (`4 de marzo de 2026`, `2026-03-04`,
`04/03/2026`) is read as a day, a month and a year and checked against those of the dates the data has;
every other number is checked against the rest. Month names are not checked: "en marzo" is often said of a
period the result does not spell out.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from safe_spending.pipeline.verification.enums import DatePart

_TOKEN = re.compile(r"(?<!\w)(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?!\d)")
_LIST_MARKER = re.compile(r"^[ \t]*\d+[.)][ \t]", re.MULTILINE)
_DIGIT_RUN = re.compile(r"\d+")
_PAGING = re.compile(r"\b(?:LIMIT|OFFSET)\s+\d+", re.IGNORECASE)

_MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_SLASH = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")
_WRITTEN = re.compile(rf"(?<!\d)(\d{{1,2}})\s+de\s+(?:{_MONTHS})(?:\s+de\s+(\d{{4}}))?(?!\d)", re.IGNORECASE)
_MONTH_YEAR = re.compile(rf"\b(?:{_MONTHS})\s+de\s+(\d{{4}})(?!\d)", re.IGNORECASE)


def iso_dates_in(text: str) -> list[tuple[int, int, int]]:
    """Each ISO date (`2026-03-04`) in the text, as (year, month, day)."""
    return [(int(year), int(month), int(day)) for year, month, day in _ISO.findall(text)]


def dates_in_answer(text: str) -> tuple[str, list[tuple[str, DatePart, int]]]:
    """The text without its dates, and each date part found in them as written, with what it is and its value."""
    found: list[tuple[str, DatePart, int]] = []

    def take(match: re.Match, parts: tuple[DatePart | None, ...]) -> str:
        for group, part in enumerate(parts, start=1):
            if part is not None and match.group(group) is not None:
                found.append((match.group(group), part, int(match.group(group))))
        return " "

    text = _ISO.sub(lambda m: take(m, (DatePart.YEAR, DatePart.MONTH, DatePart.DAY)), text)
    text = _SLASH.sub(lambda m: take(m, (DatePart.DAY, DatePart.MONTH, DatePart.YEAR)), text)
    text = _WRITTEN.sub(lambda m: take(m, (DatePart.DAY, DatePart.YEAR)), text)
    text = _MONTH_YEAR.sub(lambda m: take(m, (DatePart.YEAR,)), text)

    return text, found


def numbers_in_answer(text: str) -> list[tuple[str, frozenset[Decimal]]]:
    """Each number as written, with the values it can mean. Numbered-list markers (`1.`) are not numbers."""
    text = _LIST_MARKER.sub("", text)

    return [(token, _readings(token)) for token in _TOKEN.findall(text)]


def numbers_in_text(text: str) -> set[Decimal]:
    """Every value a source text (question, assumptions, a concept) can be said to contain.

    Lenient on purpose: this is the allowed side. Digit runs inside codes are included, so a concept that
    says `RECIBO 4521` lets the answer quote `4521`."""
    values: set[Decimal] = set()
    for token in _TOKEN.findall(text):
        values |= _readings(token)
    for run in _DIGIT_RUN.findall(text):
        values.add(Decimal(run))

    return values


def numbers_in_sql(sql: str) -> set[Decimal]:
    """The SQL's numbers other than dates (which are `DateParts`) and `LIMIT`/`OFFSET`, which are paging."""
    return numbers_in_text(text=_ISO.sub(" ", _PAGING.sub("", sql)))


def numbers_in_cell(value: object) -> set[Decimal]:
    """A cell's numbers; a date cell has none, its parts are `DateParts`."""
    if value is None or isinstance(value, (bool, date, datetime)):
        return set()
    if isinstance(value, str):
        return numbers_in_text(text=value)
    try:
        return {abs(Decimal(str(value)))}
    except InvalidOperation:
        return set()


def _readings(token: str) -> frozenset[Decimal]:
    readings = set()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        readings.add(Decimal(token.replace(".", "").replace(",", ".")))  # 1.234,56 and the thousands of 1.234
    if re.fullmatch(r"\d+[.,]\d+", token):
        readings.add(Decimal(token.replace(",", ".")))  # 12,50, and 12.5 or the decimals of 1.234
    if token.isdigit():
        readings.add(Decimal(token))

    return frozenset(readings)
