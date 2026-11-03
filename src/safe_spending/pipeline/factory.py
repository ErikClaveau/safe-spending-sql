"""The assistant wired from its real adapters: what the evals and the demo both run (ADR-009).

One place decides how the generator, validator, executor, synthesizer and verifier are put together, so
the app can never drift from what the evals measure. What differs between callers (the database, whether
to synthesize, where to trace) is a parameter.
"""

from datetime import date
from pathlib import Path

from anthropic import Anthropic

from safe_spending.clock import FixedClock, SystemClock
from safe_spending.pipeline.assistant import Assistant, TraceContext
from safe_spending.pipeline.execution import PostgresQueryExecutor
from safe_spending.pipeline.generation import LLMSQLGenerator
from safe_spending.pipeline.llm import AnthropicLLMProvider
from safe_spending.pipeline.schema import PostgresSchemaProvider
from safe_spending.pipeline.synthesis import LLMAnswerSynthesizer
from safe_spending.pipeline.tracing import JsonlTraceSink
from safe_spending.pipeline.validation import SqlglotSQLValidator
from safe_spending.pipeline.verification import ResultNumberVerifier

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_ATTEMPTS = 3


def build_assistant(
        model: str,
        prompt_version: str,
        max_corrections: int,
        reference_date: date,
        *,
        dbname: str | None = None,
        synthesize: bool = False,
        effort: str = DEFAULT_EFFORT,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        trace_dir: Path | None = None,
        trace_context: TraceContext | None = None
) -> tuple[Assistant, str]:
    """The assistant over `dbname` (`None`: the development database), and the version of the schema it
    shows the model.

    With `synthesize` it also writes the answer text from the result (same model and protocol as the SQL),
    and every number in that text is checked against the result. With `trace_dir` every question is traced
    to a JSONL file there (ADR-007); it needs `trace_context`, and the file is named after the real date,
    not the frozen one of the dataset. The database is always reached as `app_reader`."""
    if (trace_dir is None) != (trace_context is None):
        raise ValueError("trace_dir and trace_context go together: tracing needs both or neither")

    schema_provider = PostgresSchemaProvider(dbname=dbname)
    llm = AnthropicLLMProvider(
        client=Anthropic(),
        model=model,
        effort=effort,
        refusal_fallback=False
    )
    clock = FixedClock(today=reference_date)
    assistant = Assistant(
        generator=LLMSQLGenerator(
            schema_provider=schema_provider,
            llm=llm,
            clock=clock,
            max_attempts=max_attempts,
            prompt_version=prompt_version,
        ),
        validator=SqlglotSQLValidator(),
        executor=PostgresQueryExecutor(dbname=dbname),
        max_corrections=max_corrections,
        synthesizer=LLMAnswerSynthesizer(
            llm=llm,
            clock=clock,
            verifier=ResultNumberVerifier()
        ) if synthesize else None,
        trace_sink=JsonlTraceSink(
            directory=trace_dir,
            clock=SystemClock()
        ) if trace_dir else None,
        trace_context=trace_context,
    )

    return assistant, schema_provider.get_schema().version
