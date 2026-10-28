"""The pipeline end to end: generate, validate, execute under RLS (plan section 7).

Week 3 stops at the query result. Answer synthesis and the check that every number in the answer
comes from the result are later stages. `user_id` comes from the caller (the authentication layer),
never from the question or the model, and the SQL is run exactly as the model wrote it.

Self-correction: if the validator rejects the SQL, or the database refuses it, the model is shown what
went wrong and writes it again, up to `max_corrections` times. The corrected SQL goes through the same
validator and the same RLS execution as the first one, so a correction never has more privileges.
A timeout is not corrected: rewording rarely makes a slow query fast, and each try costs seconds.

Synthesis: with a synthesizer, a query that ran gets its answer written from the whole result (every column,
so what third parties wrote in a concept reaches the model: the prompt and, later, the numeric check defend
against it). Without one the assistant stops at the result, as the golden-set evals do.

Tracing (ADR-007): with a `trace_sink` and a `trace_context`, every request is handed to the sink as a
`RequestTrace` with the user as a pseudonym. A failing sink is logged and never changes the answer.
"""

import logging
import uuid

from safe_spending.pipeline.assistant.ports import TraceSink
from safe_spending.pipeline.assistant.pseudonym import pseudonymize
from safe_spending.pipeline.assistant.schemas import (
    AssistantOutcome,
    AssistantResult,
    AssistantRound,
    RequestTrace,
    TraceContext,
)
from safe_spending.pipeline.execution import ExecutionErrorKind, QueryExecutor
from safe_spending.pipeline.generation import Correction, CorrectionKind, GeneratorAction, SQLGenerator
from safe_spending.pipeline.synthesis import AnswerSynthesizer
from safe_spending.pipeline.validation import SQLValidator

logger = logging.getLogger(__name__)


class Assistant:
    def __init__(
            self,
            generator: SQLGenerator,
            validator: SQLValidator,
            executor: QueryExecutor,
            *,
            max_corrections: int = 1,
            synthesizer: AnswerSynthesizer | None = None,
            trace_sink: TraceSink | None = None,
            trace_context: TraceContext | None = None
    ) -> None:
        if max_corrections < 0:
            raise ValueError("max_corrections cannot be negative")
        if (trace_sink is None) != (trace_context is None):
            raise ValueError("trace_sink and trace_context go together")

        self._generator = generator
        self._validator = validator
        self._executor = executor
        self._max_corrections = max_corrections
        self._synthesizer = synthesizer
        self._trace_sink = trace_sink
        self._trace_context = trace_context

    def ask(
            self,
            user_id: int,
            question: str
    ) -> AssistantResult:
        result = self._run(
            user_id=user_id,
            question=question
        )
        self._trace(
            user_id=user_id,
            result=result
        )

        return result

    def _trace(
            self,
            user_id: int,
            result: AssistantResult
    ) -> None:
        if self._trace_sink is None:
            return

        try:
            self._trace_sink.emit(RequestTrace(
                request_id=str(uuid.uuid4()),
                user_ref=pseudonymize(
                    user_id=user_id,
                    salt=self._trace_context.user_salt
                ),
                commit_sha=self._trace_context.commit_sha,
                result=result
            ))
        except Exception:
            logger.exception("The trace sink failed; the answer is not affected")

    def _run(
            self,
            user_id: int,
            question: str
    ) -> AssistantResult:
        earlier: list[AssistantRound] = []

        while True:
            generation = self._generator.generate(
                question=question,
                corrections=tuple(r.correction for r in earlier)
            )
            response = generation.response

            if response is None:
                return self._result(
                    question=question,
                    outcome=AssistantOutcome.GENERATION_FAILED,
                    generation=generation,
                    earlier=earlier
                )
            if response.action is GeneratorAction.CLARIFY:
                return self._result(
                    question=question,
                    outcome=AssistantOutcome.CLARIFY,
                    generation=generation,
                    earlier=earlier
                )
            if response.action is GeneratorAction.REFUSE:
                return self._result(
                    question=question,
                    outcome=AssistantOutcome.REFUSED,
                    generation=generation,
                    earlier=earlier
                )

            validation = self._validator.validate(sql=response.sql)
            execution = None
            if validation.valid:
                execution = self._executor.execute(
                    user_id=user_id,
                    sql=response.sql
                )
                if execution.ok:
                    synthesis = self._synthesize(
                        question=question,
                        response=response,
                        execution=execution
                    )
                    failed = synthesis is not None and synthesis.answer is None
                    return self._result(
                        question=question,
                        outcome=AssistantOutcome.SYNTHESIS_FAILED if failed else AssistantOutcome.ANSWERED,
                        generation=generation,
                        earlier=earlier,
                        validation=validation,
                        execution=execution,
                        synthesis=synthesis
                    )

            correction = self._correction(
                response=response,
                validation=validation,
                execution=execution
            )
            if correction is None or len(earlier) >= self._max_corrections:
                outcome = AssistantOutcome.REJECTED if not validation.valid else AssistantOutcome.EXECUTION_FAILED
                return self._result(
                    question=question,
                    outcome=outcome,
                    generation=generation,
                    earlier=earlier,
                    validation=validation,
                    execution=execution
                )

            earlier.append(AssistantRound(
                generation=generation,
                validation=validation,
                execution=execution,
                correction=correction
            ))

    def _synthesize(
            self,
            question,
            response,
            execution
    ):
        if self._synthesizer is None:
            return None

        return self._synthesizer.synthesize(
            question=question,
            sql=response.sql,
            result=execution.result,
            assumptions=response.message
        )

    @staticmethod
    def _correction(
            response,
            validation,
            execution
    ) -> Correction | None:
        if not validation.valid:
            return Correction(
                response=response,
                kind=CorrectionKind.REJECTED,
                detail="; ".join(validation.violations)
            )
        if execution.error_kind is ExecutionErrorKind.DATABASE_ERROR:
            return Correction(
                response=response,
                kind=CorrectionKind.EXECUTION_ERROR,
                detail=execution.error
            )

        return None

    @staticmethod
    def _result(
            question,
            outcome,
            generation,
            earlier,
            validation=None,
            execution=None,
            synthesis=None
    ) -> AssistantResult:
        return AssistantResult(
            question=question,
            outcome=outcome,
            generation=generation,
            validation=validation,
            execution=execution,
            corrections=tuple(earlier),
            synthesis=synthesis
        )
