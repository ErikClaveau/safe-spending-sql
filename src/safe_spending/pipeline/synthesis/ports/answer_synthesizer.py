"""The `AnswerSynthesizer` port: from a query result to the text the user reads (plan section 7).

The numbers in the answer come from the result, never from the model's arithmetic; checking that is the
numeric verification's job, not this port's. The result's text columns (concept, counterparty) are
third-party text and reach the model as data: resisting what they say is part of this stage's contract.
"""

from typing import Protocol

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.synthesis.schemas import SynthesisResult


class AnswerSynthesizer(Protocol):
    def synthesize(
            self,
            question: str,
            sql: str,
            result: QueryResult,
            assumptions: str | None = None
    ) -> SynthesisResult: ...
