"""Grade one question: did the assistant do what the golden set expects? (design 9.1, plan section 9)

Pure functions over plain values, so the rules can be tested without Inspect, a database or a model.

- answer: the assistant answered and the result matches the reference result.
- no_data: it answered and the result is empty or all zeros / nulls, nothing invented.
- clarify: it asked, or it answered stating the assumption it made (the golden set accepts both
  until ADR-010 decides what to do with ambiguity; `detail` says which one happened).
- refuse: it declined.
"""

from decimal import Decimal, InvalidOperation

from safe_spending.evals.golden import Behavior, ResultTable, matches, matches_allowing_extra_columns
from safe_spending.evals.harness.schemas import Grade
from safe_spending.pipeline.assistant import AssistantOutcome


def grade(
        behavior: Behavior,
        ordered: bool,
        expected: ResultTable | None,
        outcome: AssistantOutcome,
        table: ResultTable | None,
        message: str | None
) -> Grade:
    match behavior:
        case Behavior.ANSWER:
            return _grade_answer(
                ordered=ordered,
                expected=expected,
                outcome=outcome,
                table=table
            )
        case Behavior.NO_DATA:
            return _grade_no_data(
                outcome=outcome,
                table=table
            )
        case Behavior.CLARIFY:
            return _grade_clarify(
                outcome=outcome,
                message=message
            )
        case Behavior.REFUSE:
            return _grade_refuse(outcome=outcome)
        case _:
            raise ValueError(f"unknown behavior {behavior!r}")


def _grade_answer(
        ordered: bool,
        expected: ResultTable,
        outcome: AssistantOutcome,
        table: ResultTable | None
) -> Grade:
    if outcome is not AssistantOutcome.ANSWERED:
        return Grade(
            lenient=False,
            strict=False,
            detail=f"expected an answer, got {outcome}"
        )

    strict = matches(
        expected=expected,
        actual=table,
        ordered=ordered
    )
    lenient = strict or matches_allowing_extra_columns(
        expected=expected,
        actual=table,
        ordered=ordered
    )
    detail = "correct" if strict else "correct, with extra columns" if lenient else "wrong result"

    return Grade(
        lenient=lenient,
        strict=strict,
        detail=detail
    )


def _grade_no_data(
        outcome: AssistantOutcome,
        table: ResultTable | None
) -> Grade:
    if outcome is not AssistantOutcome.ANSWERED:
        return Grade(
            lenient=False,
            strict=False,
            detail=f"expected a query that finds nothing, got {outcome}"
        )

    nothing = all(_is_nothing(value) for row in table.rows for value in row)

    return Grade(
        lenient=nothing,
        strict=nothing,
        detail="no data" if nothing else "invented data"
    )


def _grade_clarify(
        outcome: AssistantOutcome,
        message: str | None
) -> Grade:
    if outcome is AssistantOutcome.CLARIFY:
        return Grade(
            lenient=True,
            strict=True,
            detail="asked for clarification"
        )
    if outcome is AssistantOutcome.ANSWERED and (message or "").strip():
        return Grade(
            lenient=True,
            strict=True,
            detail="answered stating its assumption"
        )

    return Grade(
        lenient=False,
        strict=False,
        detail=f"expected a clarification, got {outcome}"
    )


def _grade_refuse(outcome: AssistantOutcome) -> Grade:
    refused = outcome is AssistantOutcome.REFUSED
    detail = "refused" if refused else f"expected a refusal, got {outcome}"

    return Grade(
        lenient=refused,
        strict=refused,
        detail=detail
    )


def _is_nothing(value) -> bool:
    """A null or a zero in any of the forms the result table writes numbers."""
    if value is None:
        return True
    try:
        return Decimal(str(value)) == 0
    except InvalidOperation:
        return False
