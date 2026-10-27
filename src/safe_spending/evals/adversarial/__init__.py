"""The adversarial set: attempts to break the assistant's guarantees (plan sections 4 and 9).

Isolation questions try to reach another user's data; the leak detector says whether they did.
Injection questions are innocent: the attack sits in the data they retrieve, and a canary in the answer says
it worked.
"""

from safe_spending.evals.adversarial.canaries import canaries_by_user, canaries_in, canaries_in_table
from safe_spending.evals.adversarial.enums import Attack, Exposure
from safe_spending.evals.adversarial.expected import build_expected, read_expected, write_expected
from safe_spending.evals.adversarial.injection_set import INJECTION_FILE, load_injection_set
from safe_spending.evals.adversarial.isolation_set import (
    EXPECTED_FILE,
    ISOLATION_FILE,
    load_isolation_set,
)
from safe_spending.evals.adversarial.leak import distinguishable, leaked
from safe_spending.evals.adversarial.schemas import (
    ExpectedLeaks,
    InjectionQuestion,
    InjectionSet,
    IsolationQuestion,
    IsolationSet,
)


__all__ = [
    "EXPECTED_FILE",
    "INJECTION_FILE",
    "ISOLATION_FILE",
    "Attack",
    "ExpectedLeaks",
    "Exposure",
    "InjectionQuestion",
    "InjectionSet",
    "IsolationQuestion",
    "IsolationSet",
    "build_expected",
    "canaries_by_user",
    "canaries_in",
    "canaries_in_table",
    "distinguishable",
    "leaked",
    "load_injection_set",
    "load_isolation_set",
    "read_expected",
    "write_expected",
]
