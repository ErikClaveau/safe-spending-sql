"""`Assistant`: which stage ends a question, and that nothing past a stage runs after it stops."""

from decimal import Decimal

import pytest

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.assistant import Assistant, AssistantOutcome
from safe_spending.pipeline.execution import ExecutionErrorKind, ExecutionResult
from safe_spending.pipeline.generation import CorrectionKind, GenerationAttempt, GenerationResult, GeneratorResponse
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
    """Answers with each response in turn (the last one repeats) and records the corrections it was given."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.corrections_seen = []

    def generate(self, question, corrections=()):
        self.corrections_seen.append(tuple(corrections))
        index = min(len(self.corrections_seen), len(self._responses)) - 1
        return generation(self._responses[index])


def ok_execution():
    return ExecutionResult(result=QueryResult(columns=("total",), rows=((10,),), truncated=False), latency_s=0.5)


def database_error(message="column does not exist"):
    return ExecutionResult(error_kind=ExecutionErrorKind.DATABASE_ERROR, error=message, latency_s=0.1)


class FakeExecutor:
    """Returns each execution in turn (the last one repeats)."""

    def __init__(self, *executions):
        self.calls = []
        self._executions = list(executions) or [ok_execution()]

    def execute(self, user_id, sql):
        self.calls.append((user_id, sql))
        return self._executions[min(len(self.calls), len(self._executions)) - 1]


def assistant(response, executor=None, **kwargs):
    executor = executor or FakeExecutor()
    generator = FakeGenerator(*response) if isinstance(response, list) else FakeGenerator(response)
    return Assistant(generator, SqlglotSQLValidator(), executor, **kwargs), executor


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
    stages = result.latency_by_stage
    assert (stages.generation_s, stages.execution_s, stages.synthesis_s) == pytest.approx((2.0, 0.5, 0.0))


# ---------------------------------------------------------------------------
# Self-correction: a rejected or failed SQL is shown to the model once, then judged as any other
# ---------------------------------------------------------------------------


def generator_of(assistant_):
    return assistant_._generator


def test_a_rejected_sql_is_corrected_and_the_corrected_one_is_what_runs():
    assistant_, executor = assistant([query(BAD_SQL), query(GOOD_SQL)])

    result = assistant_.ask(8, "¿Cuánto gasté?")

    assert result.outcome is AssistantOutcome.ANSWERED
    assert result.sql == GOOD_SQL
    assert executor.calls == [(8, GOOD_SQL)]  # the rejected SQL never ran
    assert len(result.corrections) == 1
    first = result.corrections[0]
    assert first.generation.response.sql == BAD_SQL
    assert not first.validation.valid and first.execution is None


def test_the_model_is_told_what_was_wrong_with_the_previous_answer():
    assistant_, _ = assistant([query(BAD_SQL), query(GOOD_SQL)])

    assistant_.ask(8, "?")

    first_call, second_call = generator_of(assistant_).corrections_seen
    assert first_call == ()
    assert len(second_call) == 1
    assert second_call[0].kind is CorrectionKind.REJECTED
    assert second_call[0].response.sql == BAD_SQL
    assert "not a semantic view" in second_call[0].detail


def test_a_database_error_is_corrected_too():
    assistant_, executor = assistant(
        [query("SELECT nope FROM v_gastos LIMIT 1"), query(GOOD_SQL)],
        FakeExecutor(database_error("column nope does not exist"), ok_execution()),
    )

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.ANSWERED
    assert [sql for _, sql in executor.calls] == ["SELECT nope FROM v_gastos LIMIT 1", GOOD_SQL]
    correction = generator_of(assistant_).corrections_seen[1][0]
    assert correction.kind is CorrectionKind.EXECUTION_ERROR
    assert "column nope does not exist" in correction.detail


def test_there_is_at_most_one_correction_by_default_and_the_last_failure_is_the_outcome():
    assistant_, executor = assistant(query(BAD_SQL))

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.REJECTED
    assert len(result.corrections) == 1
    assert len(generator_of(assistant_).corrections_seen) == 2
    assert executor.calls == []


def test_a_database_error_that_stays_is_reported_as_an_execution_failure():
    assistant_, _ = assistant(query(GOOD_SQL), FakeExecutor(database_error()))

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.EXECUTION_FAILED
    assert len(result.corrections) == 1


def test_correction_can_be_switched_off():
    assistant_, _ = assistant(query(BAD_SQL), max_corrections=0)

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.REJECTED
    assert result.corrections == ()
    assert len(generator_of(assistant_).corrections_seen) == 1


def test_more_corrections_are_allowed_when_asked_for():
    assistant_, _ = assistant([query(BAD_SQL), query(BAD_SQL), query(GOOD_SQL)], max_corrections=2)

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.ANSWERED
    assert len(result.corrections) == 2
    assert len(generator_of(assistant_).corrections_seen[2]) == 2  # both earlier answers are replayed


def test_a_timeout_is_not_corrected():
    timeout = ExecutionResult(error_kind=ExecutionErrorKind.TIMEOUT, error="canceling statement", latency_s=5.0)
    assistant_, executor = assistant(query(GOOD_SQL), FakeExecutor(timeout))

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.EXECUTION_FAILED
    assert result.corrections == ()
    assert len(executor.calls) == 1


def test_a_correction_can_end_in_a_clarification():
    assistant_, executor = assistant([query(BAD_SQL), GeneratorResponse(action="clarify", message="¿Qué periodo?")])

    result = assistant_.ask(8, "?")

    assert result.outcome is AssistantOutcome.CLARIFY
    assert len(result.corrections) == 1
    assert executor.calls == []


def test_cost_and_latency_cover_every_try():
    assistant_, _ = assistant([query(BAD_SQL), query(GOOD_SQL)])

    result = assistant_.ask(8, "?")

    assert result.cost_usd == Decimal("0.02")  # two generations
    assert result.latency_s == pytest.approx(4.5)  # 2.0 + 2.0 generating, 0.5 executing the corrected one
    assert result.latency_by_stage.generation_s == pytest.approx(4.0)
    assert result.latency_by_stage.execution_s == pytest.approx(0.5)


def test_a_negative_number_of_corrections_is_refused():
    with pytest.raises(ValueError, match="max_corrections"):
        assistant(query(GOOD_SQL), max_corrections=-1)
