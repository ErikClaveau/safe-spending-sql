"""The pipeline end to end: generate, validate, execute under RLS (plan section 7).

Week 3 stops at the query result. Answer synthesis and the check that every number in the answer
comes from the result are later stages. `user_id` comes from the caller (the authentication layer),
never from the question or the model, and the SQL is run exactly as the model wrote it.
"""

from safe_spending.pipeline.assistant.schemas import AssistantOutcome, AssistantResult
from safe_spending.pipeline.execution import QueryExecutor
from safe_spending.pipeline.generation import GeneratorAction, SQLGenerator
from safe_spending.pipeline.validation import SQLValidator


class Assistant:
    def __init__(
            self,
            generator: SQLGenerator,
            validator: SQLValidator,
            executor: QueryExecutor
    ) -> None:
        self._generator = generator
        self._validator = validator
        self._executor = executor

    def ask(
            self,
            user_id: int,
            question: str
    ) -> AssistantResult:
        generation = self._generator.generate(question=question)
        response = generation.response

        if response is None:
            return AssistantResult(
                question=question,
                outcome=AssistantOutcome.GENERATION_FAILED,
                generation=generation
            )
        if response.action is GeneratorAction.CLARIFY:
            return AssistantResult(
                question=question,
                outcome=AssistantOutcome.CLARIFY,
                generation=generation
            )
        if response.action is GeneratorAction.REFUSE:
            return AssistantResult(
                question=question,
                outcome=AssistantOutcome.REFUSED,
                generation=generation
            )

        validation = self._validator.validate(sql=response.sql)
        if not validation.valid:
            return AssistantResult(
                question=question,
                outcome=AssistantOutcome.REJECTED,
                generation=generation,
                validation=validation,
            )

        execution = self._executor.execute(
            user_id=user_id,
            sql=response.sql
        )
        outcome = AssistantOutcome.ANSWERED if execution.ok else AssistantOutcome.EXECUTION_FAILED

        return AssistantResult(
            question=question,
            outcome=outcome,
            generation=generation,
            validation=validation,
            execution=execution
        )
