"""The `TraceSink` port: where the trace of each request goes (ADR-007).

A sink must not decide the outcome of a request: the assistant ignores its failures.
"""

from typing import Protocol

from safe_spending.pipeline.assistant.schemas.request_trace import RequestTrace


class TraceSink(Protocol):
    def emit(
            self,
            trace: RequestTrace
    ) -> None: ...
