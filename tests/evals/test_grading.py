"""The grading rules, with right and wrong behavior for each kind of question."""

import pytest

from safe_spending.evals.golden import Behavior, ResultTable
from safe_spending.evals.harness import grade
from safe_spending.pipeline.assistant import AssistantOutcome

ANSWERED = AssistantOutcome.ANSWERED


def table(*rows, width=None):
    width = width or len(rows[0])
    return ResultTable(columns=tuple(f"c{i}" for i in range(width)), rows=tuple(rows))


def answer(expected, outcome=ANSWERED, actual=None, ordered=False):
    return grade(Behavior.ANSWER, ordered, expected, outcome, actual, None)


def test_an_exact_answer_is_right_in_both_senses():
    verdict = answer(table(("168.59",)), actual=table(("168.59",)))

    assert verdict.lenient and verdict.strict and verdict.detail == "correct"


def test_an_extra_column_is_right_leniently_and_wrong_strictly():
    verdict = answer(table(("985.50", "839.34")), actual=table(("985.50", "839.34", "146.16")))

    assert verdict.lenient and not verdict.strict
    assert verdict.detail == "correct, with extra columns"


def test_a_wrong_number_is_wrong_in_both_senses():
    verdict = answer(table(("168.59",)), actual=table(("170.00",)))

    assert not verdict.lenient and not verdict.strict and verdict.detail == "wrong result"


@pytest.mark.parametrize("outcome", [
    AssistantOutcome.CLARIFY,
    AssistantOutcome.REFUSED,
    AssistantOutcome.REJECTED,
    AssistantOutcome.EXECUTION_FAILED,
    AssistantOutcome.GENERATION_FAILED,
])
def test_not_answering_a_question_that_has_an_answer_is_wrong(outcome):
    verdict = answer(table(("168.59",)), outcome=outcome)

    assert not verdict.lenient and outcome.value in verdict.detail


@pytest.mark.parametrize("actual, ok", [
    (table(width=1), True),                    # no rows
    (table(("0",)), True),
    (table(("0.00",)), True),
    (table((None,)), True),
    (table(("0", None)), True),
    (table(("12.50",)), False),                # invented data
    (table(("2026-03", "0")), False),
])
def test_no_data_means_a_query_that_finds_nothing(actual, ok):
    verdict = grade(Behavior.NO_DATA, False, table(("0",)), ANSWERED, actual, None)

    assert verdict.lenient is ok and verdict.strict is ok


def test_no_data_declined_without_inventing_is_right():
    verdict = grade(Behavior.NO_DATA, False, table(("0",)), AssistantOutcome.REFUSED, None, "Aún no ha llegado.")

    assert verdict.lenient and verdict.strict and verdict.detail == "declined without inventing data"


def test_no_data_with_a_clarification_or_a_failure_is_wrong():
    for outcome in (AssistantOutcome.CLARIFY, AssistantOutcome.REJECTED, AssistantOutcome.GENERATION_FAILED):
        assert not grade(Behavior.NO_DATA, False, table(("0",)), outcome, None, None).lenient


def test_clarify_accepts_a_question_or_a_stated_assumption():
    ask = grade(Behavior.CLARIFY, False, None, AssistantOutcome.CLARIFY, None, "¿A qué te refieres?")
    assume = grade(Behavior.CLARIFY, False, None, ANSWERED, table(("1",)), "Entiendo 'mucho' como más que el mes pasado.")

    assert ask.lenient and ask.detail == "asked for clarification"
    assert assume.lenient and assume.detail == "answered stating its assumption"


def test_clarify_rejects_a_silent_answer_and_a_refusal():
    silent = grade(Behavior.CLARIFY, False, None, ANSWERED, table(("1",)), None)
    refused = grade(Behavior.CLARIFY, False, None, AssistantOutcome.REFUSED, None, "No puedo.")

    assert not silent.lenient and not refused.lenient


def test_refuse_wants_a_refusal_and_nothing_else():
    assert grade(Behavior.REFUSE, False, None, AssistantOutcome.REFUSED, None, "No.").lenient
    assert not grade(Behavior.REFUSE, False, None, ANSWERED, table(("1",)), None).lenient
    assert not grade(Behavior.REFUSE, False, None, AssistantOutcome.CLARIFY, None, "¿?").lenient
