"""`AnthropicLLMProvider` against a fake client: no network, no key (ADR-004, ADR-006)."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from safe_spending.pipeline.generation import GeneratorResponse
from safe_spending.pipeline.llm import AnthropicLLMProvider, LLMMessage, LLMRequest, LLMRole, TokenUsage
from safe_spending.pipeline.llm.schemas import ModelPricing

MODEL = "claude-sonnet-5-5"
SQL = "SELECT SUM(gasto_eur) FROM v_gastos LIMIT 1"


def tool_use(**input_):
    return SimpleNamespace(type="tool_use", name="respond", input=input_)


def text(value):
    return SimpleNamespace(type="text", text=value)


def reply(content, *, model=MODEL, stop_reason="tool_use", usage=None):
    return SimpleNamespace(
        content=content,
        model=model,
        stop_reason=stop_reason,
        usage=usage or SimpleNamespace(
            input_tokens=1000, output_tokens=200, cache_read_input_tokens=None, cache_creation_input_tokens=None
        ),
        _request_id="req_1",
    )


class FakeClient:
    """Records the calls of both endpoints and answers with `response`."""

    def __init__(self, response):
        self.calls = []
        self.messages = SimpleNamespace(create=lambda **kw: self._call("messages", kw, response))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: self._call("beta", kw, response)))

    def _call(self, endpoint, kwargs, response):
        self.calls.append((endpoint, kwargs))
        return response


def request():
    return LLMRequest(
        system="Eres un asistente de gastos.",
        messages=(LLMMessage(role=LLMRole.USER, content="¿Cuánto gasté en septiembre?"),),
        output_name="respond",
        output_description="Your answer.",
        output_schema=GeneratorResponse.model_json_schema(),
    )


def provider(response, **kwargs):
    client = FakeClient(response)
    return AnthropicLLMProvider(client, MODEL, **kwargs), client


def test_the_structured_output_is_the_tool_input_as_json():
    llm, _ = provider(reply([tool_use(action="query", sql=SQL, message="Este mes: septiembre.")]))

    response = llm.complete(request())

    assert json.loads(response.structured_output) == {"action": "query", "sql": SQL, "message": "Este mes: septiembre."}
    assert GeneratorResponse.model_validate_json(response.structured_output).sql == SQL


def test_a_reply_without_the_tool_call_has_no_structured_output():
    llm, _ = provider(reply([text("Claro, te lo cuento.")], stop_reason="end_turn"))

    response = llm.complete(request())

    assert response.structured_output is None
    assert response.text == "Claro, te lo cuento."


def test_a_call_to_another_tool_is_not_the_output():
    llm, _ = provider(reply([SimpleNamespace(type="tool_use", name="other", input={"a": 1})]))

    assert llm.complete(request()).structured_output is None


def test_the_request_uses_a_strict_tool_with_auto_choice_and_no_sampling():
    llm, client = provider(reply([tool_use(action="query", sql=SQL)]), refusal_fallback=False)

    llm.complete(request())

    endpoint, kwargs = client.calls[0]
    assert endpoint == "messages"
    assert kwargs["tool_choice"] == {"type": "auto"}
    assert kwargs["tools"][0]["strict"] is True
    assert kwargs["tools"][0]["input_schema"]["required"] == ["action"]
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["model"] == MODEL
    assert "respond" in kwargs["system"]
    assert kwargs["messages"] == [{"role": "user", "content": "¿Cuánto gasté en septiembre?"}]
    assert not {"temperature", "top_p", "top_k", "thinking"} & kwargs.keys()


def test_refusal_fallback_goes_through_the_beta_endpoint_and_is_on_by_default():
    llm, client = provider(reply([tool_use(action="query", sql=SQL)]))

    llm.complete(request())

    endpoint, kwargs = client.calls[0]
    assert endpoint == "beta"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["fallbacks"] == "default"


def test_usage_cost_and_request_id_are_reported():
    usage = SimpleNamespace(
        input_tokens=1000, output_tokens=200, cache_read_input_tokens=500, cache_creation_input_tokens=100
    )
    llm, _ = provider(reply([tool_use(action="query", sql=SQL)], usage=usage))

    response = llm.complete(request())

    assert response.usage == TokenUsage(input_tokens=1000, output_tokens=200, cache_read_tokens=500, cache_write_tokens=100)
    # 1000*2 + 200*10 + 500*0.20 + 100*2.50 = 4350 -> USD per million
    assert response.cost_usd == Decimal("4350") / Decimal(1_000_000) == Decimal("0.00435")
    assert response.request_id == "req_1"
    assert response.latency_s >= 0


def test_the_cost_follows_the_model_that_served_the_request():
    llm, _ = provider(reply([tool_use(action="query", sql=SQL)], model="claude-opus-5-5"))

    # A fallback to Opus is priced as Opus: 1000*4 + 200*20 = 8000
    assert llm.complete(request()).cost_usd == Decimal("0.008")


def test_an_unknown_model_has_no_cost_rather_than_a_wrong_one():
    llm, _ = provider(reply([tool_use(action="query", sql=SQL)], model="some-other-model"))

    response = llm.complete(request())

    assert response.cost_usd is None
    assert response.model == "some-other-model"


def test_a_refusal_is_reported_not_raised():
    llm, _ = provider(reply([], stop_reason="refusal"))

    response = llm.complete(request())

    assert response.stop_reason == "refusal"
    assert response.structured_output is None


def test_pricing_can_be_overridden():
    free = {MODEL: ModelPricing(input=Decimal(0), output=Decimal(0), cache_read=Decimal(0), cache_write=Decimal(0))}
    llm, _ = provider(reply([tool_use(action="query", sql=SQL)]), pricing=free)

    assert llm.complete(request()).cost_usd == Decimal(0)
