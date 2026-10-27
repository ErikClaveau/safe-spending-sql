"""The adversarial set: attempts to break the assistant's guarantees (plan sections 4 and 9).

Isolation questions try to reach another user's data; the leak detector says whether they did.
The data-injection set (canaries) comes with answer synthesis.
"""

from safe_spending.evals.adversarial.enums import Attack
from safe_spending.evals.adversarial.expected import build_expected, read_expected, write_expected
from safe_spending.evals.adversarial.isolation_set import (
    EXPECTED_FILE,
    ISOLATION_FILE,
    load_isolation_set,
)
from safe_spending.evals.adversarial.leak import distinguishable, leaked
from safe_spending.evals.adversarial.schemas import ExpectedLeaks, IsolationQuestion, IsolationSet


__all__ = [
    "EXPECTED_FILE",
    "ISOLATION_FILE",
    "Attack",
    "ExpectedLeaks",
    "IsolationQuestion",
    "IsolationSet",
    "build_expected",
    "distinguishable",
    "leaked",
    "load_isolation_set",
    "read_expected",
    "write_expected",
]
