"""The `LLMProvider` port: one call to a model, with the provider's details kept behind it.

A provider returns what the model produced and never judges it: a missing or malformed
structured output is an invalid attempt for the caller to record and retry (ADR-006).
"""

from typing import Protocol

from safe_spending.pipeline.llm.schemas import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    def complete(
            self,
            request: LLMRequest
    ) -> LLMResponse: ...
