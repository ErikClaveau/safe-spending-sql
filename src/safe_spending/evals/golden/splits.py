"""The held-out part of the golden set.

Improving prompts and documentation against the same questions the result is reported on makes the
number rise by fitting those questions. So a third of the set is held out: it is scored every round
and reported next to the rest, but a change is never chosen because of a test question.

The rule is mechanical, so nobody picks questions: within each category, in id order, every third
question (the 3rd, 6th, 9th...) is a test question. `derive_test_ids` is that rule and
`splits_v0.yaml` is its output, frozen: a test checks that the file still equals the rule, and adding
questions later means a new set (v1), not editing this one.
"""

from pathlib import Path

import yaml

from safe_spending.evals.golden.enums import Split
from safe_spending.evals.golden.golden_set import GOLDEN_DIR, GoldenSet

SPLITS_FILE = GOLDEN_DIR / "splits_v0.yaml"
EVERY = 3


def derive_test_ids(golden: GoldenSet) -> tuple[str, ...]:
    """The test questions the rule picks: every third question of each category, in id order."""
    by_category: dict = {}
    for question in golden.questions:
        by_category.setdefault(question.category, []).append(question.id)

    picked = [ids[index] for ids in by_category.values() for index in range(EVERY - 1, len(ids), EVERY)]

    return tuple(sorted(picked))


def load_test_ids(path: Path = SPLITS_FILE) -> frozenset[str]:
    return frozenset(yaml.safe_load(path.read_text(encoding="utf-8"))["test"])


def split_of(
        question_id: str,
        test_ids: frozenset[str]
) -> Split:
    return Split.TEST if question_id in test_ids else Split.DEV
