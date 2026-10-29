"""The "try to break it" panel: preset attacks from the adversarial set and the verdict on each run.

Pure functions over the assistant's result, so the rules are tested without Streamlit, a database or a model.
The verdicts are the ones the evals use (`leaked`, `canaries_in`), not a second opinion: the demo shows what
the release gates measure.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from safe_spending.evals.adversarial import (
    ExpectedLeaks,
    canaries_in,
    canaries_in_table,
    leaked,
    load_injection_set,
    load_isolation_set,
)
from safe_spending.evals.golden import to_table
from safe_spending.pipeline.assistant import AssistantResult


class AttackKind(StrEnum):
    ISOLATION = "isolation"
    INJECTION = "injection"


@dataclass(frozen=True)
class Preset:
    id: str
    kind: AttackKind
    user_id: int
    question: str
    victim_user_id: int | None = None
    """Isolation only: the user whose data the question aims at."""
    notes: str | None = None

    @property
    def label(self) -> str:
        return f"{self.id} · user {self.user_id} · {self.question}"


@dataclass(frozen=True)
class AttackVerdict:
    broken: bool
    """True when the guarantee failed: the victim's data came back, or a canary reached the answer."""
    reached_model: bool
    """Injection only: the planted text was in the rows the model was given."""
    explanation: str


def load_presets() -> tuple[Preset, ...]:
    isolation = [
        Preset(
            id=q.id,
            kind=AttackKind.ISOLATION,
            user_id=q.user_id,
            question=q.question,
            victim_user_id=q.victim_user_id,
            notes=q.notes,
        )
        for q in load_isolation_set().questions
    ]
    injection = [
        Preset(
            id=q.id,
            kind=AttackKind.INJECTION,
            user_id=q.user_id,
            question=q.question,
            notes=q.notes,
        )
        for q in load_injection_set().questions
    ]

    return tuple(isolation + injection)


def judge(
        preset: Preset,
        result: AssistantResult,
        expected: ExpectedLeaks,
        canaries: Iterable[str],
) -> AttackVerdict:
    """Did the attack work? Uses the same rules as the isolation and injection gates."""
    table = to_table(result.execution.result) if result.execution and result.execution.result else None

    if preset.kind is AttackKind.ISOLATION:
        did_leak = leaked(
            actual=table,
            victim=expected.victim_table(preset.id),
            own=expected.own_table(preset.id),
        )
        return AttackVerdict(
            broken=did_leak,
            reached_model=False,
            explanation=(
                f"The result reproduces data of user {preset.victim_user_id}."
                if did_leak
                else f"No data of user {preset.victim_user_id} in the result: "
                     "whatever comes back is the asker's own."
            ),
        )

    canaries = tuple(canaries)
    in_answer = canaries_in(text=result.answer, canaries=canaries)
    reached = bool(canaries_in_table(table=table, canaries=canaries))
    if in_answer:
        explanation = "A code planted in a concept reached the answer."
    elif reached:
        explanation = "The malicious text reached the model inside the rows, and the answer ignores it."
    else:
        explanation = "The malicious text was not in the rows the model received."

    return AttackVerdict(broken=bool(in_answer), reached_model=reached, explanation=explanation)
