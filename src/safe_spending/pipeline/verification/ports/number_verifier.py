"""The `NumberVerifier` port: every number in an answer must come from what the query produced (plan section 6).

Numbers are computed by SQL, never by the model. A figure the model counted or added itself is not in the
result, so it is reported as untraced and the answer is not shown.
"""

from datetime import date
from typing import Protocol

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.verification.schemas import NumericVerification


class NumberVerifier(Protocol):
    def verify(
            self,
            answer: str,
            result: QueryResult,
            *,
            question: str,
            sql: str,
            assumptions: str | None,
            today: date
    ) -> NumericVerification: ...
