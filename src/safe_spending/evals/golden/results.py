"""A query result in a form that can be written to JSON and compared (design 9.1: execution accuracy).

The comparison ignores the order of the rows unless the question says it matters, ignores column
names (a model may alias differently), and tolerates a cent in numbers.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.db.query_result import QueryResult

TOLERANCE = Decimal("0.01")


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


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if _is_number(a) and _is_number(b):
        return abs(Decimal(str(a)) - Decimal(str(b))) <= TOLERANCE
    return a == b


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
