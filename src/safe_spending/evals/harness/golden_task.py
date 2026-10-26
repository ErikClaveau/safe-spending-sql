"""The golden set as an Inspect AI task (ADR-003): the assistant is the solver, the golden set the scorer.

Run it from the repo root (the reference database is rebuilt first, so it needs Docker's Postgres):

    uv run --env-file .env inspect eval src/safe_spending/evals/harness/golden_task.py --max-samples 4

`--limit 8` runs a few questions; `-T split=dev` or `-T split=test` runs only that part (see
`evals/golden/splits.py`). `-T max_corrections=0` turns self-correction off. Task options go with `-T`, e.g. `-T model=claude-haiku-5-5`. The model is
ours (`LLMProvider`), not Inspect's, which is why the task pins `mockllm/model` as Inspect's model.

Refusal fallback is off here (ADR-003 protocol): every answer comes from the one model under test, and a
refusal counts as a failed generation instead of being rescued by another model.
"""

import anyio
from anthropic import Anthropic
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, grouped, mean, metric, scorer, stderr
from inspect_ai.scorer import SampleScore, Value
from inspect_ai.solver import Generate, TaskState, solver

from safe_spending.clock import FixedClock
from safe_spending.evals.golden import ResultTable, Split, load_golden_set, load_test_ids, read_expected, split_of
from safe_spending.evals.golden.dataset import GOLDEN_DATABASE, build_reference_database
from safe_spending.evals.harness.grading import grade
from safe_spending.evals.harness.schemas import AssistantRun, SampleMetadata, TaskMetadata
from safe_spending.pipeline.assistant import Assistant
from safe_spending.pipeline.execution import PostgresQueryExecutor
from safe_spending.pipeline.generation import PROMPT_VERSION, LLMSQLGenerator
from safe_spending.pipeline.llm import AnthropicLLMProvider
from safe_spending.pipeline.schema import PostgresSchemaProvider
from safe_spending.pipeline.validation import SqlglotSQLValidator

DEFAULT_MODEL = "claude-sonnet-5-5"
EFFORT = "medium"
MAX_ATTEMPTS = 3
RESULT_KEY = "assistant_result"


@task
def golden_set(
        model: str = DEFAULT_MODEL,
        rebuild: bool = True,
        split: str = "all",
        prompt_version: str = PROMPT_VERSION,
        max_corrections: int = 1
) -> Task:
    golden = load_golden_set()
    test_ids = load_test_ids()
    expected = read_expected()
    if rebuild:
        build_reference_database()

    schema_provider = PostgresSchemaProvider(dbname=GOLDEN_DATABASE)
    assistant = Assistant(
        generator=LLMSQLGenerator(
            schema_provider=schema_provider,
            llm=AnthropicLLMProvider(
                client=Anthropic(),
                model=model,
                effort=EFFORT,
                refusal_fallback=False
            ),
            clock=FixedClock(today=golden.reference_date),
            max_attempts=MAX_ATTEMPTS,
            prompt_version=prompt_version,
        ),
        validator=SqlglotSQLValidator(),
        executor=PostgresQueryExecutor(dbname=GOLDEN_DATABASE),
        max_corrections=max_corrections,
    )

    samples = [
        Sample(
            id=q.id,
            input=q.question,
            target=q.behavior.value,
            metadata=SampleMetadata(
                user_id=q.user_id,
                category=q.category,
                split=split_of(
                    question_id=q.id,
                    test_ids=test_ids
                ),
                difficulty=q.difficulty,
                behavior=q.behavior,
                ordered=q.ordered,
                expected=expected.answers.get(q.id),
            ).model_dump(mode="json"),
        )
        for q in golden.questions
        if split == "all" or split_of(question_id=q.id, test_ids=test_ids) == Split(split)
    ]

    return Task(
        dataset=MemoryDataset(
            samples=samples,
            name="golden_v0"
        ),
        solver=run_assistant(assistant=assistant),
        scorer=[
            execution_accuracy(),
            execution_accuracy_strict(),
            cost_usd(),
            latency_s()
        ],
        model="mockllm/model",
        metadata=TaskMetadata(
            model=model,
            effort=EFFORT,
            refusal_fallback=False,
            max_attempts=MAX_ATTEMPTS,
            max_corrections=max_corrections,
            prompt_version=prompt_version,
            schema_version=schema_provider.get_schema().version,
            dataset_version=golden.dataset_version,
        ).model_dump(),
    )


@solver
def run_assistant(assistant: Assistant):
    async def solve(
            state: TaskState,
            generate: Generate
    ) -> TaskState:
        meta = state.metadata_as(metadata_cls=SampleMetadata)
        result = await anyio.to_thread.run_sync(
            assistant.ask,
            meta.user_id,
            state.input_text
        )

        run = AssistantRun.from_result(result=result)
        state.metadata[RESULT_KEY] = run.model_dump(mode="json")
        state.output.completion = result.sql or result.message or result.outcome.value
        return state

    return solve


def _observed(state: TaskState) -> AssistantRun:
    return AssistantRun.model_validate(obj=state.metadata[RESULT_KEY])


def _grade(state: TaskState):
    observed = _observed(state=state)
    meta = state.metadata_as(metadata_cls=SampleMetadata)

    return grade(
        behavior=meta.behavior,
        ordered=meta.ordered,
        expected=ResultTable.from_json(meta.expected) if meta.expected else None,
        outcome=observed.outcome,
        table=observed.table,
        message=observed.message,
    )


@scorer(metrics=[accuracy(), stderr(), grouped(accuracy(), "category"), grouped(accuracy(), "split")])
def execution_accuracy():
    """Headline: the right answer, extra columns forgiven; or the right behavior (clarify, no data, refuse)."""

    async def score(
            state: TaskState,
            target: Target
    ) -> Score:
        verdict = _grade(state=state)
        return Score(
            value=CORRECT if verdict.lenient else INCORRECT,
            answer=state.output.completion,
            explanation=verdict.detail,
            metadata={
                "outcome": _observed(state).outcome.value,
                "corrections": _observed(state).corrections
            },
        )

    return score


@scorer(metrics=[accuracy(), stderr(), grouped(accuracy(), "split")])
def execution_accuracy_strict():
    """The same with the columns exactly as the reference has them, as benchmarks define it."""

    async def score(state: TaskState, target: Target) -> Score:
        verdict = _grade(state=state)
        return Score(
            value=CORRECT if verdict.strict else INCORRECT,
            explanation=verdict.detail
        )

    return score


@metric
def total():
    def compute(scores: list[SampleScore]) -> Value:
        return sum(s.score.as_float() for s in scores)

    return compute


@scorer(metrics=[mean(), total()])
def cost_usd():
    """USD spent on the model, per question and in total. A question with no known price counts as 0."""

    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=_observed(state).cost_usd or 0.0)

    return score


@scorer(metrics=[mean()])
def latency_s():
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=_observed(state).latency_s)

    return score
