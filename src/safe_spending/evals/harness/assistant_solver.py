"""What every Inspect task of this project shares: the assistant under test and the solver that runs it."""

from datetime import date
from pathlib import Path

import anyio
from inspect_ai.solver import Generate, TaskState, solver

from safe_spending.evals.golden.dataset import GOLDEN_DATABASE
from safe_spending.evals.harness.schemas import AssistantRun
from safe_spending.pipeline import factory
from safe_spending.pipeline.assistant import Assistant
from safe_spending.pipeline.factory import DEFAULT_MAX_ATTEMPTS as MAX_ATTEMPTS
from safe_spending.pipeline.factory import DEFAULT_MODEL
from safe_spending.pipeline.factory import DEFAULT_EFFORT as EFFORT
from safe_spending.pipeline.tracing import trace_context_from_environment

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
    """The shared assistant (`pipeline.factory`) over the golden reference database, traced to `trace_dir`
    (ADR-007; `None` turns it off) with a fixed salt, since the eval users are synthetic."""
    return factory.build_assistant(
        model=model,
        prompt_version=prompt_version,
        max_corrections=max_corrections,
        reference_date=reference_date,
        dbname=GOLDEN_DATABASE,
        synthesize=synthesize,
        trace_dir=trace_dir,
        trace_context=trace_context_from_environment(default_salt=EVAL_USER_SALT) if trace_dir else None,
    )


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
