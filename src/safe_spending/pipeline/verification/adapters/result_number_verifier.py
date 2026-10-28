"""`NumberVerifier` over the query result: a number is traced if it is in a cell, the question or the SQL.

What counts as a source: every cell of the result (the whole result, not only the rows the model was shown),
the question and the stated assumptions (the user said "3 meses"; the period is theirs) and the SQL's
literals. Dates are checked apart, by day, month and year, against the dates of the result, the SQL and today
(the prompt gives it). A count of rows, a sum or a percentage the model worked out is not in any of them, so
it fails: figures are computed by SQL. Numbers written as words ("tres") are not checked.
"""

from datetime import date, datetime
from decimal import Decimal

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.verification.adapters.number_extraction import (
    dates_in_answer,
    iso_dates_in,
    numbers_in_answer,
    numbers_in_cell,
    numbers_in_sql,
    numbers_in_text,
)
from safe_spending.pipeline.verification.enums import DatePart
from safe_spending.pipeline.verification.ports import NumberVerifier
from safe_spending.pipeline.verification.schemas import DateParts, NumericVerification


class ResultNumberVerifier(NumberVerifier):
    def verify(
            self,
            answer: str,
            result: QueryResult,
            *,
            question: str,
            sql: str,
            assumptions: str | None,
            today: date
    ) -> NumericVerification:
        allowed: set[Decimal] = numbers_in_sql(sql=sql) | numbers_in_text(text=question)
        dates = DateParts()
        dates.add_date(value=today)
        for year, month, day in iso_dates_in(text=sql):
            dates.add(
                year=year,
                month=month,
                day=day
            )
        if assumptions:
            allowed |= numbers_in_text(text=assumptions)
        for row in result.rows:
            for cell in row:
                allowed |= numbers_in_cell(value=cell)
                if isinstance(cell, (date, datetime)):
                    dates.add_date(value=cell)

        rest, date_tokens = dates_in_answer(text=answer)
        found = numbers_in_answer(text=rest)
        untraced = [
            token for token, part, value in date_tokens
            if not dates.has(
                part=part,
                value=value
            ) and Decimal(value=value) not in allowed
        ]
        untraced += [
            token for token, readings in found
            if not readings & allowed and not any(
                self._is_a_year_of(
                    dates=dates,
                    reading=reading
                ) for reading in readings
            )
        ]

        return NumericVerification(
            checked=tuple([token for token, _, _ in date_tokens] + [token for token, _ in found]),
            untraced=tuple(untraced)
        )

    @staticmethod
    def _is_a_year_of(
            dates: DateParts,
            reading: Decimal
    ) -> bool:
        """A bare year ("de 2024 y 2025") is as good as the year of a date; days and months alone are not."""
        return reading == reading.to_integral_value() and dates.has(
            part=DatePart.YEAR,
            value=int(reading)
        )
