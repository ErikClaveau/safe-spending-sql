"""`LLMProvider` over the Anthropic Messages API (ADR-004, ADR-006).

The structured output goes through a tool with `strict: true`. Claude Sonnet 5.5 and Opus 5.5
reject a forced `tool_choice` (HTTP 400), so the choice is `auto` and the system prompt asks for the
tool: the schema is guaranteed when the model calls it, and a reply without the call comes back with
`structured_output=None` for the caller to count as a failed attempt.

No `temperature` is sent (those models reject non-default sampling); variation is controlled by the
pinned model and `effort`. The client reads its credentials from the environment.
"""

import json
import time

from anthropic import Anthropic

from safe_spending.pipeline.llm.adapters.anthropic_pricing import ANTHROPIC_PRICING
from safe_spending.pipeline.llm.ports import LLMProvider
from safe_spending.pipeline.llm.schemas import LLMRequest, LLMResponse, ModelPricing, TokenUsage

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicLLMProvider(LLMProvider):
    def __init__(
            self,
            client: Anthropic,
            model: str,
            *,
            effort: str = "medium",
            max_tokens: int = 16000,
            refusal_fallback: bool = True,
            pricing: dict[str, ModelPricing] | None = None
    ) -> None:
        self._client = client
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens
        self._refusal_fallback = refusal_fallback
        self._pricing = ANTHROPIC_PRICING if pricing is None else pricing

    def complete(
            self,
            request: LLMRequest
    ) -> LLMResponse:
        params = dict(
            model=self._model,
            max_tokens=self._max_tokens,
            system=f"{request.system}\n\nAnswer only by calling the `{request.output_name}` tool.",
            messages=[message.model_dump(mode="json") for message in request.messages],
            tools=[{
                "name": request.output_name,
                "description": request.output_description,
                "input_schema": request.output_schema,
                "strict": True,
            }],
            tool_choice={"type": "auto"},
            output_config={"effort": self._effort},
        )

        started = time.perf_counter()
        if self._refusal_fallback:
            response = self._client.beta.messages.create(
                betas=[_FALLBACK_BETA],
                fallbacks="default", **params
            )
        else:
            response = self._client.messages.create(**params)
        latency = time.perf_counter() - started

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=response.usage.cache_read_input_tokens or 0,
            cache_write_tokens=response.usage.cache_creation_input_tokens or 0,
        )
        pricing = self._pricing.get(response.model)

        return LLMResponse(
            structured_output=self._structured_output(
                response=response,
                output_name=request.output_name
            ),
            text="".join(block.text for block in response.content if block.type == "text"),
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            cost_usd=pricing.cost(usage) if pricing else None,
            latency_s=latency,
            request_id=response._request_id,
        )

    @staticmethod
    def _structured_output(
            response,
            output_name: str
    ) -> str | None:
        for block in response.content:
            if block.type == "tool_use" and block.name == output_name:
                return json.dumps(
                    obj=block.input,
                    ensure_ascii=False
                )
        return None
