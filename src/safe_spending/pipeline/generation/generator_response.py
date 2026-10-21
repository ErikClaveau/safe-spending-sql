from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.pipeline.generation.generator_action import GeneratorAction


class GeneratorResponse(BaseModel):
    """The structured answer of the SQL generator: the contract of the `SQLGenerator` port (ADR-006).

    One flat object, because providers force a tool schema more reliably than a union. This
    validates the shape only: `sql` is still untrusted text for the validator and for RLS (ADR-002).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    action: GeneratorAction = Field(
        description="`query` to answer with SQL, `clarify` to ask the user, `refuse` if out of scope."
    )
    sql: str | None = Field(
        default=None,
        description="A single SELECT over the semantic views. Only with `query`; null otherwise."
    )
    message: str | None = Field(
        default=None,
        description="Spanish text for the user. Required with `clarify` and `refuse`; with `query` it "
                    "states the assumptions made, if any."
    )

    @model_validator(mode="after")
    def _fields_match_the_action(self) -> Self:
        has_sql = bool(self.sql and self.sql.strip())
        has_message = bool(self.message and self.message.strip())

        if self.action is GeneratorAction.QUERY:
            if not has_sql:
                raise ValueError("action `query` needs a non-empty `sql`")
        else:
            if self.sql is not None:
                raise ValueError(f"action `{self.action}` must not carry `sql`")
            if not has_message:
                raise ValueError(f"action `{self.action}` needs a non-empty `message`")

        return self
