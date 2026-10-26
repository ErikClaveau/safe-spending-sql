"""A query result in a form that can be written to JSON and compared (design 9.1: execution accuracy).

The comparison ignores the order of the rows unless the question says it matters, ignores column
names (a model may alias differently), tolerates a cent in numbers and takes a month written as
'2026-03' and as its first day, '2026-03-01', to be the same. `matches` is strict about
the columns (execution accuracy as benchmarks define it); `matches_allowing_extra_columns` also
accepts a result that has the requested columns plus others.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from itertools import permutations
from math import perm

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.db.query_result import QueryResult

TOLERANCE = Decimal("0.01")
MONTH = re.compile(r"^\d{4}-\d{2}$")
FIRST_OF_MONTH = re.compile(r"^\d{4}-\d{2}-01$")
MAX_COLUMN_CHOICES = 10_000  # beyond this many ways to pick the columns, extra columns are not searched


class ResultTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    columns: tuple[str, ...]
    rows: tuple[tuple, ...] = Field(
        description="JSON-friendly values: int, str, bool or None (money and dates as text)"
    )

    def to_json(self) -> dict:
        return {"columns": list(self.columns), "rows": [list(row) for row in self.rows]}

    @classmethod
    def from_json(cls, data: dict) -> "ResultTable":
        return cls(columns=data["columns"], rows=data["rows"])


def to_table(result: QueryResult) -> ResultTable:
    return ResultTable(
        columns=result.columns,
        rows=tuple(tuple(_jsonable(v) for v in row) for row in result.rows),
    )


def _jsonable(value):
    if isinstance(value, Decimal):
        return format(value, "f")  # never scientific notation
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def matches(
        expected: ResultTable,
        actual: ResultTable,
        *,
        ordered: bool
) -> bool:
    """True when `actual` answers like `expected`."""
    if len(expected.rows) != len(actual.rows):
        return False
    if any(len(a) != len(b) for a, b in zip(expected.rows, actual.rows)):
        return False

    left, right = list(expected.rows), list(actual.rows)
    if not ordered:
        left, right = sorted(left, key=_sort_key), sorted(right, key=_sort_key)

    return all(_same(a, b) for row_a, row_b in zip(left, right) for a, b in zip(row_a, row_b))


def matches_allowing_extra_columns(
        expected: ResultTable,
        actual: ResultTable,
        *,
        ordered: bool
) -> bool:
    """True when some choice of `actual`'s columns, in some order, answers like `expected`.

    A model that adds a column nobody asked for (a difference, a percentage) still gave the right
    answer, so extra columns do not count against it. Rows must still match exactly: this never
    forgives a different number of rows or a wrong value in a requested column.
    """
    width = len(expected.columns)
    available = len(actual.columns)

    if available < width:
        return False
    if available == width:
        return matches(
            expected=expected,
            actual=actual,
            ordered=ordered
        )
    if perm(available, width) > MAX_COLUMN_CHOICES:
        return False

    for picked in permutations(range(available), width):
        projection = ResultTable(
            columns=tuple(actual.columns[i] for i in picked),
            rows=tuple(tuple(row[i] for i in picked) for row in actual.rows),
        )
        if matches(
                expected=expected,
                actual=projection,
                ordered=ordered
        ):
            return True

    return False


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if _is_month_and_its_first_day(
            month=a,
            first_day=b
    ) or _is_month_and_its_first_day(
        month=b,
        first_day=a
    ):
        return True
    if _is_number(value=a) and _is_number(value=b):
        return abs(Decimal(str(a)) - Decimal(str(b))) <= TOLERANCE
    return a == b


def _is_month_and_its_first_day(month, first_day) -> bool:
    """'2026-03' and '2026-03-01' name the same month: a model may truncate with `date_trunc` where the
    reference formats with `to_char`. Only the first of the month, so a real date is never a month."""
    return (
            isinstance(month, str) and isinstance(first_day, str)
            and MONTH.match(month) is not None
            and FIRST_OF_MONTH.match(first_day) is not None
            and first_day.startswith(month)
    )


def _is_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | Decimal):
        return True
    if isinstance(value, str):
        try:
            Decimal(value)
        except ArithmeticError:
            return False
        return value.lstrip("-").replace(".", "", 1).isdigit()  # '2026-03' and 'ES12' are text, not numbers
    return False


def _sort_key(row: tuple) -> tuple:
    return tuple("" if v is None else str(v) for v in row)
