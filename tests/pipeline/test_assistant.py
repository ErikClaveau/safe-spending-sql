"""`Assistant`: which stage ends a question, and that nothing past a stage runs after it stops."""

from decimal import Decimal

import pytest

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.assistant import Assistant, AssistantOutcome
from safe_spending.pipeline.execution import ExecutionErrorKind, ExecutionResult
from safe_spending.pipeline.generation import GenerationAttempt, GenerationResult, GeneratorResponse
from safe_spending.pipeline.llm import LLMResponse, TokenUsage
from safe_spending.pipeline.validation import SqlglotSQLValidator

GOOD_SQL = "SELECT SUM(gasto_eur) FROM v_gastos LIMIT 1"
BAD_SQL = "SELECT * FROM transactions LIMIT 5"


def generation(response: GeneratorResponse | None) -> GenerationResult:
    llm = LLMResponse(
        structured_output=response.model_dump_json() if response else None,
        text="",
        model="claude-sonnet-5-5",
        stop_reason="tool_use",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
        cost_usd=Decimal("0.01"),
        latency_s=2.0,
        request_id=None,
    )
    return GenerationResult(
        response=response,
        attempts=(GenerationAttempt.from_llm(llm),),
        prompt_version="v1",
        schema_version="abc",
    )


class FakeGenerator:
    def __init__(self, response):
        self._response = response

    def generate(self, question):
        return generation(self._response)


class FakeExecutor:
    def __init__(self, execution=None):
        self.calls = []
        self._execution = execution or ExecutionResult(
            result=QueryResult(columns=("total",), rows=((10,),), truncated=False), latency_s=0.5
        )

    def execute(self, user_id, sql):
        self.calls.append((user_id, sql))
        return self._execution


def assistant(response, executor=None):
    executor = executor or FakeExecutor()
    return Assistant(FakeGenerator(response), SqlglotSQLValidator(), executor), executor


def query(sql):
    return GeneratorResponse(action="query", sql=sql)


def test_a_valid_query_is_executed_as_the_given_user_exactly_as_written():
    assistant_, executor = assistant(query(GOOD_SQL))

    result = assistant_.ask(8, "¿Cuánto gasté?")

    assert result.outcome is AssistantOutcome.ANSWERED
    assert executor.calls == [(8, GOOD_SQL)]
    assert result.execution.result.rows == ((10,),)
    assert result.validation.valid
    assert result.sql == GOOD_SQL


def test_sql_that_fails_validation_is_never_executed():
    assistant_, executor = assistant(query(BAD_SQL))

    result = assistant_.ask(8, "dame todo")

    assert result.outcome is AssistantOutcome.REJECTED
    assert executor.calls == []
    assert result.execution is None
    assert any("not a semantic view" in v for v in result.validation.violations)


@pytest.mark.parametrize("action, outcome", [
    ("clarify", AssistantOutcome.CLARIFY),
    ("refuse", AssistantOutcome.REFUSED),
])
def test_clarify_and_refuse_end_before_validation_and_execution(action, outcome):
    assistant_, executor = assistant(GeneratorResponse(action=action, message="Dime más."))

    result = assistant_.ask(8, "¿Estoy gastando mucho?")

    assert result.outcome is outcome
    assert result.message == "Dime más."
    assert result.validation is None and result.execution is None
    assert executor.calls == []


def test_a_generation_that_never_validated_ends_the_question():
    assistant_, executor = assistant(None)

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.GENERATION_FAILED
    assert result.sql is None
    assert executor.calls == []


def test_a_database_failure_is_reported_with_its_error():
    failed = ExecutionResult(error_kind=ExecutionErrorKind.TIMEOUT, error="canceling statement", latency_s=5.0)
    assistant_, _ = assistant(query(GOOD_SQL), FakeExecutor(failed))

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.EXECUTION_FAILED
    assert result.execution.error_kind is ExecutionErrorKind.TIMEOUT


def test_cost_and_latency_add_up_over_the_stages():
    assistant_, _ = assistant(query(GOOD_SQL))

    result = assistant_.ask(8, "?")

    assert result.cost_usd == Decimal("0.01")
    assert result.latency_s == pytest.approx(2.5)  # 2.0 generation + 0.5 execution
