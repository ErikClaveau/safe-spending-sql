"""The generator's structured response (ADR-006): the shape is validated, never trusted."""

import json

import pytest
from pydantic import ValidationError

from safe_spending.pipeline.generation import GenerationAttempt, GeneratorAction, GeneratorResponse

SQL = "SELECT SUM(gasto_eur) FROM v_gastos LIMIT 1"


def test_query_with_sql_is_valid():
    response = GeneratorResponse(action="query", sql=SQL)

    assert response.action is GeneratorAction.QUERY
    assert response.message is None


def test_query_may_state_its_assumptions():
    assert GeneratorResponse(action="query", sql=SQL, message="Entiendo 'este mes' como septiembre.").message


@pytest.mark.parametrize("sql", [None, "", "   \n"])
def test_query_without_sql_is_refused(sql):
    with pytest.raises(ValidationError, match="non-empty `sql`"):
        GeneratorResponse(action="query", sql=sql)


@pytest.mark.parametrize("action", ["clarify", "refuse"])
def test_clarify_and_refuse_need_a_message_and_no_sql(action):
    assert GeneratorResponse(action=action, message="¿A qué mes te refieres?").sql is None

    with pytest.raises(ValidationError, match="non-empty `message`"):
        GeneratorResponse(action=action, message="  ")

    with pytest.raises(ValidationError, match="must not carry `sql`"):
        GeneratorResponse(action=action, sql=SQL, message="hola")


def test_unknown_action_and_extra_fields_are_refused():
    with pytest.raises(ValidationError):
        GeneratorResponse(action="no_data", message="nada")

    with pytest.raises(ValidationError):
        GeneratorResponse(action="query", sql=SQL, user_id=2)


def test_response_is_immutable():
    response = GeneratorResponse(action="query", sql=SQL)

    with pytest.raises(ValidationError):
        response.sql = "DROP TABLE x"


def test_the_json_schema_is_what_the_provider_will_force():
    schema = GeneratorResponse.model_json_schema()

    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"action", "sql", "message"}
    assert schema["required"] == ["action"]


def test_attempt_from_valid_raw_keeps_response_and_raw():
    raw = json.dumps({"action": "query", "sql": SQL})

    attempt = GenerationAttempt.from_raw(raw)

    assert attempt.valid
    assert attempt.error is None
    assert attempt.raw == raw
    assert attempt.response.sql == SQL


@pytest.mark.parametrize("raw", [
    "esto no es json",
    json.dumps({"action": "query"}),
    json.dumps({"action": "drop", "sql": SQL}),
])
def test_attempt_from_invalid_raw_keeps_the_error_for_the_trace(raw):
    attempt = GenerationAttempt.from_raw(raw)

    assert not attempt.valid
    assert attempt.response is None
    assert attempt.error
    assert attempt.raw == raw


def test_attempt_needs_exactly_one_outcome():
    with pytest.raises(ValidationError):
        GenerationAttempt(raw="{}")

    with pytest.raises(ValidationError):
        GenerationAttempt(raw="{}", response=GeneratorResponse(action="query", sql=SQL), error="x")
