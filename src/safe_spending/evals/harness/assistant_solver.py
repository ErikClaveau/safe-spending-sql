"""What every Inspect task of this project shares: the assistant under test and the solver that runs it."""

from datetime import date
from pathlib import Path

import anyio
from anthropic import Anthropic
from inspect_ai.solver import Generate, TaskState, solver

from safe_spending.clock import FixedClock, SystemClock
from safe_spending.evals.golden.dataset import GOLDEN_DATABASE
from safe_spending.evals.harness.schemas import AssistantRun
from safe_spending.pipeline.assistant import Assistant
from safe_spending.pipeline.execution import PostgresQueryExecutor
from safe_spending.pipeline.generation import LLMSQLGenerator
from safe_spending.pipeline.llm import AnthropicLLMProvider
from safe_spending.pipeline.schema import PostgresSchemaProvider
from safe_spending.pipeline.synthesis import LLMAnswerSynthesizer
from safe_spending.pipeline.tracing import JsonlTraceSink, trace_context_from_environment
from safe_spending.pipeline.validation import SqlglotSQLValidator
from safe_spending.pipeline.verification import ResultNumberVerifier

DEFAULT_MODEL = "claude-sonnet-5-5"
EFFORT = "medium"
MAX_ATTEMPTS = 3
RESULT_KEY = "assistant_result"
TRACE_DIR = Path("logs/traces")
EVAL_USER_SALT = "eval-synthetic-users"  # the eval users are synthetic: no secret needed


def build_assistant(
        model: str,
        prompt_version: str,
        max_corrections: int,
        reference_date: date,
        synthesize: bool = False,
        trace_dir: Path | None = TRACE_DIR
) -> tuple[Assistant, str]:
    """The assistant over the reference database, and the version of the schema it shows the model.

    With `synthesize` it also writes the answer text from the result (same model and protocol as the SQL),
    and every number in that text is checked against the result. Every question is also traced to a JSONL
    file in `trace_dir` (ADR-007; `None` turns it off); the file is named after the real date, not the
    frozen one of the dataset."""
    schema_provider = PostgresSchemaProvider(dbname=GOLDEN_DATABASE)
    llm = AnthropicLLMProvider(
        client=Anthropic(),
        model=model,
        effort=EFFORT,
        refusal_fallback=False
    )
    clock = FixedClock(today=reference_date)
    assistant = Assistant(
        generator=LLMSQLGenerator(
            schema_provider=schema_provider,
            llm=llm,
            clock=clock,
            max_attempts=MAX_ATTEMPTS,
            prompt_version=prompt_version,
        ),
        validator=SqlglotSQLValidator(),
        executor=PostgresQueryExecutor(dbname=GOLDEN_DATABASE),
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
        trace_context=trace_context_from_environment(default_salt=EVAL_USER_SALT) if trace_dir else None,
    )

    return assistant, schema_provider.get_schema().version


@solver
def run_assistant(assistant: Assistant):
    async def solve(
            state: TaskState,
            generate: Generate
    ) -> TaskState:
        user_id = state.metadata["user_id"]
        result = await anyio.to_thread.run_sync(
            assistant.ask,
            user_id,
            state.input_text
        )

        run = AssistantRun.from_result(result=result)
        state.metadata[RESULT_KEY] = run.model_dump(mode="json")
        state.output.completion = result.sql or result.message or result.outcome.value
        return state

    return solve


def observed(state: TaskState) -> AssistantRun:
    return AssistantRun.model_validate(obj=state.metadata[RESULT_KEY])
