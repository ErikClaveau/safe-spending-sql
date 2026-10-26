"""The pipeline end to end: generate, validate, execute under RLS (plan section 7).

Week 3 stops at the query result. Answer synthesis and the check that every number in the answer
comes from the result are later stages. `user_id` comes from the caller (the authentication layer),
never from the question or the model, and the SQL is run exactly as the model wrote it.

Self-correction: if the validator rejects the SQL, or the database refuses it, the model is shown what
went wrong and writes it again, up to `max_corrections` times. The corrected SQL goes through the same
validator and the same RLS execution as the first one, so a correction never has more privileges.
A timeout is not corrected: rewording rarely makes a slow query fast, and each try costs seconds.
"""

from safe_spending.pipeline.assistant.schemas import AssistantOutcome, AssistantResult, AssistantRound
from safe_spending.pipeline.execution import ExecutionErrorKind, QueryExecutor
from safe_spending.pipeline.generation import Correction, CorrectionKind, GeneratorAction, SQLGenerator
from safe_spending.pipeline.validation import SQLValidator


class Assistant:
    def __init__(
            self,
            generator: SQLGenerator,
            validator: SQLValidator,
            executor: QueryExecutor,
            *,
            max_corrections: int = 1
    ) -> None:
        if max_corrections < 0:
            raise ValueError("max_corrections cannot be negative")

        self._generator = generator
        self._validator = validator
        self._executor = executor
        self._max_corrections = max_corrections

    def ask(
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
                    return self._result(
                        question=question,
                        outcome=AssistantOutcome.ANSWERED,
                        generation=generation,
                        earlier=earlier,
                        validation=validation,
                        execution=execution
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

    @staticmethod
    def _correction(response, validation, execution) -> Correction | None:
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
    def _result(question, outcome, generation, earlier, validation=None, execution=None) -> AssistantResult:
        return AssistantResult(
            question=question,
            outcome=outcome,
            generation=generation,
            validation=validation,
            execution=execution,
            corrections=tuple(earlier)
        )
