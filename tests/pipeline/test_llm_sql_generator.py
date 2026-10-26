"""`LLMSQLGenerator`: prompt, retries and the record of every attempt, with a scripted provider (ADR-006)."""

import json
from datetime import date
from decimal import Decimal

import pytest

from safe_spending.clock import FixedClock
from safe_spending.pipeline.generation import (
    PROMPT_VERSION,
    Correction,
    CorrectionKind,
    GeneratorResponse,
    LLMSQLGenerator,
    render_system_prompt,
)
from safe_spending.pipeline.llm import LLMResponse, LLMRole, TokenUsage
from safe_spending.pipeline.schema import CategoryDoc, ColumnDoc, SemanticSchema, ViewDoc

TODAY = date(2026, 9, 15)
SQL = "SELECT SUM(gasto_eur) FROM v_gastos LIMIT 1"
QUESTION = "¿Cuánto gasté en supermercados este mes?"

SCHEMA = SemanticSchema(
    views=(
        ViewDoc(
            name="v_gastos",
            description="Gastos del usuario.",
            columns=(ColumnDoc(name="gasto_eur", data_type="numeric(12,2)", description="Importe del gasto."),),
        ),
    ),
    categories=(
        CategoryDoc(name="Supermercados", group_name="Alimentación"),
        CategoryDoc(name="Restaurantes y bares", group_name="Alimentación"),
        CategoryDoc(name="Gasolina", group_name="Transporte"),
    ),
)


def llm_response(structured_output=None, *, text="", stop_reason="tool_use", cost="0.004"):
    return LLMResponse(
        structured_output=structured_output,
        text=text,
        model="claude-sonnet-5-5",
        stop_reason=stop_reason,
        usage=TokenUsage(input_tokens=1000, output_tokens=200),
        cost_usd=None if cost is None else Decimal(cost),
        latency_s=1.5,
        request_id="req_1",
    )


def good():
    return llm_response(json.dumps({"action": "query", "sql": SQL}))


class ScriptedLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


class CountingSchemaProvider:
    def __init__(self):
        self.calls = 0

    def get_schema(self):
        self.calls += 1
        return SCHEMA


def generator(*responses, **kwargs):
    llm = ScriptedLLM(*responses)
    schema_provider = CountingSchemaProvider()
    return LLMSQLGenerator(schema_provider, llm, FixedClock(TODAY), **kwargs), llm, schema_provider


def test_a_valid_first_attempt_is_returned_with_its_metadata():
    sql_generator, llm, _ = generator(good())

    result = sql_generator.generate(QUESTION)

    assert result.response.sql == SQL
    assert len(result.attempts) == 1
    assert result.attempts[0].llm.request_id == "req_1"
    assert result.prompt_version == PROMPT_VERSION
    assert result.schema_version == SCHEMA.version
    assert result.cost_usd == Decimal("0.004")
    assert len(llm.requests) == 1


def test_the_request_carries_the_prompt_the_question_and_the_contract():
    sql_generator, llm, _ = generator(good())

    sql_generator.generate(QUESTION)

    request = llm.requests[0]
    assert request.system == render_system_prompt(SCHEMA, TODAY)
    assert [(m.role, m.content) for m in request.messages] == [(LLMRole.USER, QUESTION)]
    assert request.output_name == "respond"
    assert set(request.output_schema["properties"]) == {"action", "sql", "message"}


def test_an_invalid_attempt_is_retried_telling_the_model_why():
    bad = llm_response(json.dumps({"action": "query"}))
    sql_generator, llm, _ = generator(bad, good())

    result = sql_generator.generate(QUESTION)

    assert [attempt.valid for attempt in result.attempts] == [False, True]
    assert result.response.sql == SQL
    retry = llm.requests[1].messages
    assert [m.role for m in retry] == [LLMRole.USER, LLMRole.ASSISTANT, LLMRole.USER]
    assert retry[1].content == bad.structured_output
    assert "no es válida" in retry[2].content and "sql" in retry[2].content
    assert result.cost_usd == Decimal("0.008")


def test_a_reply_without_the_tool_call_is_retried_too():
    sql_generator, llm, _ = generator(llm_response(text="Claro, te lo cuento.", stop_reason="end_turn"), good())

    result = sql_generator.generate(QUESTION)

    assert result.attempts[0].error.startswith("the model did not call the tool")
    assert llm.requests[1].messages[1].content == "Claro, te lo cuento."


def test_attempts_are_bounded_and_every_failure_is_kept():
    bad = llm_response("no es json")
    sql_generator, llm, _ = generator(bad, bad, bad, good(), max_attempts=3)

    result = sql_generator.generate(QUESTION)

    assert result.response is None
    assert len(result.attempts) == 3
    assert not any(attempt.valid for attempt in result.attempts)
    assert len(llm.requests) == 3


def test_a_provider_refusal_is_not_retried():
    sql_generator, llm, _ = generator(llm_response(stop_reason="refusal"), good())

    result = sql_generator.generate(QUESTION)

    assert result.response is None
    assert len(result.attempts) == 1
    assert len(llm.requests) == 1


def test_the_cost_is_unknown_if_any_attempt_has_no_price():
    sql_generator, _, _ = generator(llm_response("no es json", cost=None), good())

    assert sql_generator.generate(QUESTION).cost_usd is None


def test_the_schema_is_read_once_per_generator():
    sql_generator, _, schema_provider = generator(good(), good())

    sql_generator.generate(QUESTION)
    sql_generator.generate(QUESTION)

    assert schema_provider.calls == 1


def test_an_empty_question_never_reaches_the_model():
    sql_generator, llm, _ = generator(good())

    with pytest.raises(ValueError, match="empty"):
        sql_generator.generate("   ")

    assert llm.requests == []


def test_at_least_one_attempt_is_required():
    with pytest.raises(ValueError, match="max_attempts"):
        generator(max_attempts=0)


def test_the_prompt_has_the_date_the_views_and_the_closed_categories():
    prompt = render_system_prompt(SCHEMA, TODAY)

    assert "2026-09-15" in prompt
    assert "### v_gastos" in prompt and "`gasto_eur` (numeric(12,2)): Importe del gasto." in prompt
    assert "- Alimentación: Supermercados, Restaurantes y bares" in prompt
    assert "- Transporte: Gasolina" in prompt
    assert "$" not in prompt


def test_every_prompt_version_stays_loadable_and_none_is_edited_in_place():
    prompts = {v: render_system_prompt(SCHEMA, TODAY, version=v) for v in ("v1", "v2", "v3")}

    assert len(set(prompts.values())) == 3
    assert "COALESCE" not in prompts["v1"]  # v1 is what the baseline and round 1 ran with
    assert PROMPT_VERSION == "v3" and render_system_prompt(SCHEMA, TODAY) == prompts["v3"]


def test_prompt_v3_adds_the_coalesce_and_default_period_rules_and_leaves_out_the_columns_rule():
    v3 = render_system_prompt(SCHEMA, TODAY, version="v3")
    v2 = render_system_prompt(SCHEMA, TODAY, version="v2")

    assert "COALESCE(SUM(...), 0)" in v3 and "todo el historial" in v3
    assert "Devuelve solo las columnas que la pregunta pide" in v2  # tried in round 2, it lowered accuracy
    assert "Devuelve solo las columnas" not in v3


def test_an_unknown_prompt_version_is_refused():
    with pytest.raises(ValueError, match="unknown prompt version"):
        render_system_prompt(SCHEMA, TODAY, version="v9")


def test_the_version_the_generator_used_is_recorded_in_the_result():
    sql_generator, llm, _ = generator(good(), prompt_version="v1")

    result = sql_generator.generate(QUESTION)

    assert result.prompt_version == "v1"
    assert llm.requests[0].system == render_system_prompt(SCHEMA, TODAY, version="v1")


def test_earlier_answers_and_what_was_wrong_with_them_are_replayed_as_turns():
    sql_generator, llm, _ = generator(good())
    rejected = Correction(
        response=GeneratorResponse(action="query", sql="SELECT * FROM transactions LIMIT 1"),
        kind=CorrectionKind.REJECTED,
        detail="table transactions is not a semantic view",
    )
    failed = Correction(
        response=GeneratorResponse(action="query", sql="SELECT nope FROM v_gastos LIMIT 1"),
        kind=CorrectionKind.EXECUTION_ERROR,
        detail='column "nope" does not exist',
    )

    sql_generator.generate(QUESTION, corrections=(rejected, failed))

    messages = llm.requests[0].messages
    assert [m.role for m in messages] == [LLMRole.USER, LLMRole.ASSISTANT, LLMRole.USER, LLMRole.ASSISTANT, LLMRole.USER]
    assert messages[0].content == QUESTION
    assert json.loads(messages[1].content) == {"action": "query", "sql": "SELECT * FROM transactions LIMIT 1"}
    assert "se rechazó antes de ejecutarse" in messages[2].content and "not a semantic view" in messages[2].content
    assert "La base de datos dio este error" in messages[4].content and '"nope"' in messages[4].content


def test_no_corrections_means_just_the_question():
    sql_generator, llm, _ = generator(good())

    sql_generator.generate(QUESTION)

    assert [m.content for m in llm.requests[0].messages] == [QUESTION]
