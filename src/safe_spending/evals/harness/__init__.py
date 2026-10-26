"""Running the assistant against the golden set: grading rules and the Inspect AI task (ADR-003)."""

from .grading import grade
from .schemas import Grade

__all__ = [
    "Grade",
    "grade",
]
