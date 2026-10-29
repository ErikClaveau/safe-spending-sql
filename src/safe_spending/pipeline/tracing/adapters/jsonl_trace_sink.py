from pathlib import Path

from safe_spending.clock import Clock
from safe_spending.pipeline.assistant.schemas.request_trace import RequestTrace


class JsonlTraceSink:
    """One JSON line per request in `traces-YYYY-MM-DD.jsonl` (the date comes from the `Clock`).

    It keeps the whole result, rows included: this is the local file for debugging, not an exporter
    (ADR-007).
    """

    def __init__(
            self,
            directory: Path,
            clock: Clock
    ) -> None:
        self._directory = directory
        self._clock = clock

    def emit(
            self,
            trace: RequestTrace
    ) -> None:
        self._directory.mkdir(
            parents=True,
            exist_ok=True
        )
        path = self._directory / f"traces-{self._clock.today().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as file:
            file.write(trace.model_dump_json() + "\n")
