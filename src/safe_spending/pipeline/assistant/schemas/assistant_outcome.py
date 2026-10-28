from enum import StrEnum


class AssistantOutcome(StrEnum):
    """How a question ended, so evals and traces can count failures by stage."""

    ANSWERED = "answered"
    CLARIFY = "clarify"
    REFUSED = "refused"
    GENERATION_FAILED = "generation_failed"
    REJECTED = "rejected"
    EXECUTION_FAILED = "execution_failed"
    SYNTHESIS_FAILED = "synthesis_failed"
