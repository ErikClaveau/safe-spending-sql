"""Tracing (ADR-007): the trace of a request, the pseudonym, the JSONL file, and a sink that fails."""

import json
from datetime import date

import pytest

from safe_spending.clock import FixedClock
from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.assistant import Assistant, AssistantOutcome, TraceContext, pseudonymize
from safe_spending.pipeline.execution import ExecutionResult
from safe_spending.pipeline.generation import GeneratorResponse
from safe_spending.pipeline.tracing import JsonlTraceSink
from safe_spending.pipeline.validation import SqlglotSQLValidator

from test_assistant import GOOD_SQL, FakeExecutor, FakeGenerator

CONTEXT = TraceContext(
    commit_sha="abc1234",
    user_salt="pepper"
)
USER_ID = 7731
TODAY = FixedClock(today=date(2026, 9, 15))


class RecordingSink:
    def __init__(self):
        self.traces = []

    def emit(self, trace):
        self.traces.append(trace)


class BrokenSink:
    def emit(self, trace):
        raise OSError("disk full")


def assistant(sink) -> Assistant:
    return Assistant(
        generator=FakeGenerator(GeneratorResponse(action="query", sql=GOOD_SQL, message="todo el historial")),
        validator=SqlglotSQLValidator(),
        executor=FakeExecutor(ExecutionResult(
            result=QueryResult(columns=("total",), rows=((10,),), truncated=False),
            latency_s=0.5
        )),
        trace_sink=sink,
        trace_context=CONTEXT
    )


def test_each_request_is_emitted_with_the_result_and_a_pseudonym():
    sink = RecordingSink()

    result = assistant(sink).ask(user_id=USER_ID, question="¿Cuánto gasté?")

    [trace] = sink.traces
    assert trace.result == result
    assert trace.commit_sha == "abc1234"
    assert trace.user_ref == pseudonymize(user_id=USER_ID, salt="pepper")
    assert str(USER_ID) not in trace.user_ref


def test_request_ids_are_different_for_each_request():
    sink = RecordingSink()
    ask = assistant(sink)

    ask.ask(user_id=USER_ID, question="a")
    ask.ask(user_id=USER_ID, question="b")

    assert sink.traces[0].request_id != sink.traces[1].request_id


def test_the_pseudonym_is_stable_and_depends_on_the_user_and_the_salt():
    assert pseudonymize(user_id=1, salt="a") == pseudonymize(user_id=1, salt="a")
    assert pseudonymize(user_id=1, salt="a") != pseudonymize(user_id=2, salt="a")
    assert pseudonymize(user_id=1, salt="a") != pseudonymize(user_id=1, salt="b")


def test_a_failing_sink_does_not_change_the_answer(caplog):
    result = assistant(BrokenSink()).ask(user_id=USER_ID, question="¿Cuánto gasté?")

    assert result.outcome is AssistantOutcome.ANSWERED
    assert "trace sink failed" in caplog.text


def test_a_sink_needs_its_context():
    with pytest.raises(ValueError):
        Assistant(generator=None, validator=None, executor=None, trace_sink=RecordingSink())


def test_the_jsonl_file_has_one_line_per_request_with_the_whole_result(tmp_path):
    sink = JsonlTraceSink(directory=tmp_path / "traces", clock=TODAY)
    ask = assistant(sink)

    first = ask.ask(user_id=USER_ID, question="a")
    ask.ask(user_id=USER_ID, question="b")

    lines = (tmp_path / "traces" / "traces-2026-09-15.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    line = json.loads(lines[0])
    assert line["result"] == json.loads(first.model_dump_json())
    assert line["result"]["execution"]["result"]["rows"] == [[10]]
    assert line["result"]["cost_usd"] is not None


def test_the_user_id_never_reaches_the_file(tmp_path):
    sink = JsonlTraceSink(directory=tmp_path, clock=TODAY)

    assistant(sink).ask(user_id=USER_ID, question="¿Cuánto gasté?")

    content = (tmp_path / "traces-2026-09-15.jsonl").read_text(encoding="utf-8")
    assert str(USER_ID) not in content
    assert pseudonymize(user_id=USER_ID, salt="pepper") in content
