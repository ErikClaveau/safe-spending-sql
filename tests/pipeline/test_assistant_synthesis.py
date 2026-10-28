"""`Assistant` with a synthesizer: the answer follows a result and only a result."""

import json
from decimal import Decimal

import pytest
from test_assistant import BAD_SQL, GOOD_SQL, FakeExecutor, assistant, database_error, query

from safe_spending.pipeline.assistant import AssistantOutcome
from safe_spending.pipeline.generation import GeneratorResponse
from safe_spending.pipeline.llm import LLMResponse, TokenUsage
from safe_spending.pipeline.synthesis import SynthesisAttempt, SynthesisResult


class FakeSynthesizer:
    def __init__(self, answer="Has gastado 10 €."):
        self.calls = []
        self._answer = answer

    def synthesize(self, question, sql, result, assumptions=None):
        self.calls.append((question, sql, result, assumptions))
        llm = LLMResponse(
            structured_output=json.dumps({"answer": self._answer}) if self._answer else None,
            text="",
            model="claude-sonnet-5-5",
            stop_reason="tool_use",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            cost_usd=Decimal("0.02"),
            latency_s=1.0,
            request_id=None,
        )
        return SynthesisResult(
            answer=self._answer,
            attempts=(SynthesisAttempt.from_llm(llm),),
            prompt_version="v1",
            rows_shown=len(result.rows),
        )


def test_without_a_synthesizer_the_assistant_stops_at_the_result():
    assistant_, _ = assistant(query(GOOD_SQL))

    result = assistant_.ask(8, "¿Cuánto gasté?")

    assert result.synthesis is None and result.answer is None
    assert result.outcome is AssistantOutcome.ANSWERED


def test_a_query_that_ran_is_followed_by_the_answer_written_from_its_result():
    synthesizer = FakeSynthesizer()
    response = GeneratorResponse(action="query", sql=GOOD_SQL, message="Todo el historial.")
    assistant_, _ = assistant(response, synthesizer=synthesizer)

    result = assistant_.ask(8, "¿Cuánto gasté?")

    assert result.outcome is AssistantOutcome.ANSWERED
    assert result.answer == "Has gastado 10 €."
    question, sql, table, assumptions = synthesizer.calls[0]
    assert (question, sql, assumptions) == ("¿Cuánto gasté?", GOOD_SQL, "Todo el historial.")
    assert table.rows == ((10,),)
    assert result.cost_usd == Decimal("0.03")
    assert result.latency_s == pytest.approx(3.5)  # 2.0 generating + 0.5 executing + 1.0 synthesizing
    assert result.latency_by_stage.synthesis_s == pytest.approx(1.0)
    assert result.latency_by_stage.total_s == pytest.approx(result.latency_s)


def test_a_synthesis_that_never_validated_ends_the_question_as_a_failure():
    assistant_, _ = assistant(query(GOOD_SQL), synthesizer=FakeSynthesizer(answer=None))

    result = assistant_.ask(8, "¿Cuánto gasté?")

    assert result.outcome is AssistantOutcome.SYNTHESIS_FAILED
    assert result.answer is None
    assert result.execution.ok  # the table is still there for the trace


@pytest.mark.parametrize("response", [
    GeneratorResponse(action="refuse", message="No puedo."),
    GeneratorResponse(action="clarify", message="¿Qué periodo?"),
    query(BAD_SQL),
])
def test_nothing_is_synthesized_when_there_is_no_result(response):
    synthesizer = FakeSynthesizer()
    assistant_, _ = assistant(response, synthesizer=synthesizer)

    result = assistant_.ask(8, "x")

    assert synthesizer.calls == [] and result.synthesis is None


def test_a_database_error_is_not_synthesized():
    synthesizer = FakeSynthesizer()
    assistant_, _ = assistant(
        query(GOOD_SQL),
        executor=FakeExecutor(database_error()),
        max_corrections=0,
        synthesizer=synthesizer
    )

    assistant_.ask(8, "x")

    assert synthesizer.calls == []
