"""`SQLGenerator` over an `LLMProvider`: prompt, structured output, bounded retries (ADR-006).

A try is retried when it is not a valid `GeneratorResponse` (no tool call, malformed input), telling
the model why. A refusal by the provider is not retried. Whether the SQL is acceptable is not decided
here; that is the validator's job. When the caller passes `corrections` (an earlier answer the validator
rejected or the database refused), they are replayed as turns of the conversation before the new try.
"""

from collections.abc import Sequence

from safe_spending.clock import Clock
from safe_spending.pipeline.generation.adapters.system_prompt import PROMPT_VERSION, render_system_prompt
from safe_spending.pipeline.generation.ports import SQLGenerator
from safe_spending.pipeline.generation.schemas import (
    Correction,
    CorrectionKind,
    GenerationAttempt,
    GenerationResult,
    GeneratorResponse,
)
from safe_spending.pipeline.llm import LLMMessage, LLMProvider, LLMRequest, LLMRole
from safe_spending.pipeline.schema import SchemaProvider, SemanticSchema

OUTPUT_NAME = "respond"
_OUTPUT_DESCRIPTION = "Your answer to the user's question: the SQL to run, a clarifying question or a refusal."
_MAX_ERROR_CHARS = 500


class LLMSQLGenerator(SQLGenerator):
    def __init__(
            self,
            schema_provider: SchemaProvider,
            llm: LLMProvider,
            clock: Clock,
            *,
            max_attempts: int = 3,
            prompt_version: str = PROMPT_VERSION
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self._schema_provider = schema_provider
        self._llm = llm
        self._clock = clock
        self._max_attempts = max_attempts
        self._prompt_version = prompt_version
        self._schema: SemanticSchema | None = None

    def generate(
            self,
            question: str,
            corrections: Sequence[Correction] = ()
    ) -> GenerationResult:
        if not question.strip():
            raise ValueError("the question is empty")

        schema = self._schema_of_the_database()
        system = render_system_prompt(
            schema=schema,
            today=self._clock.today(),
            version=self._prompt_version
        )
        messages = [
            LLMMessage(
                role=LLMRole.USER,
                content=question
            )
        ]
        for correction in corrections:
            messages += self._correction_turns(correction=correction)
        attempts: list[GenerationAttempt] = []

        for _ in range(self._max_attempts):
            llm_response = self._llm.complete(request=LLMRequest(
                system=system,
                messages=tuple(messages),
                output_name=OUTPUT_NAME,
                output_description=_OUTPUT_DESCRIPTION,
                output_schema=GeneratorResponse.model_json_schema(),
            ))
            attempt = GenerationAttempt.from_llm(llm=llm_response)
            attempts.append(attempt)

            if attempt.valid or llm_response.stop_reason == "refusal":
                break

            messages += self._feedback(attempt=attempt)

        return GenerationResult(
            response=attempts[-1].response,
            attempts=tuple(attempts),
            prompt_version=self._prompt_version,
            schema_version=schema.version,
        )

    def _schema_of_the_database(self) -> SemanticSchema:
        # The semantic layer does not change while a generator lives: read it once
        if self._schema is None:
            self._schema = self._schema_provider.get_schema()
        return self._schema

    @staticmethod
    def _correction_turns(correction: Correction) -> list[LLMMessage]:
        detail = correction.detail[:_MAX_ERROR_CHARS]
        if correction.kind is CorrectionKind.REJECTED:
            problem = f"Tu consulta se rechazó antes de ejecutarse: {detail}\nReescríbela cumpliendo las reglas."
        else:
            problem = f"La base de datos dio este error al ejecutar tu consulta: {detail}\nCorrígela."

        return [
            LLMMessage(role=LLMRole.ASSISTANT, content=correction.response.model_dump_json(exclude_none=True)),
            LLMMessage(
                role=LLMRole.USER,
                content=f"{problem} Responde de nuevo llamando a la herramienta `{OUTPUT_NAME}`."
            ),
        ]

    @staticmethod
    def _feedback(attempt: GenerationAttempt) -> list[LLMMessage]:
        previous = attempt.raw or (attempt.llm.text if attempt.llm else "") or "(sin respuesta)"
        error = attempt.error[:_MAX_ERROR_CHARS]

        return [
            LLMMessage(role=LLMRole.ASSISTANT, content=previous),
            LLMMessage(
                role=LLMRole.USER,
                content=f"Tu respuesta anterior no es válida: {error}\n"
                        f"Responde de nuevo llamando a la herramienta `{OUTPUT_NAME}` con una respuesta válida."
            ),
        ]
