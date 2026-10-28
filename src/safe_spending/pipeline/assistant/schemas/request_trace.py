from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.assistant.schemas.assistant_result import AssistantResult


class RequestTrace(BaseModel):
    """One request as the trace sink receives it (plan section 10, ADR-007).

    The model, prompt version and schema version are already inside `result` (in its generation).
    `user_ref` is a pseudonym, never the user id.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    request_id: str
    user_ref: str = Field(description="Salted hash of the user id (see `pseudonymize`).")
    commit_sha: str
    result: AssistantResult
