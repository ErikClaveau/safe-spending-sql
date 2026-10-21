"""The golden set: questions about the evaluation users, each with the SQL that answers it."""

from safe_spending.evals.golden.enums import Behavior, Category, Difficulty
from safe_spending.evals.golden.expected import ExpectedAnswers, build_expected, read_expected, write_expected
from safe_spending.evals.golden.golden_set import EXPECTED_FILE, GOLDEN_FILE, GoldenSet, load_golden_set
from safe_spending.evals.golden.question import GoldenQuestion
from safe_spending.evals.golden.results import ResultTable, matches, to_table
from safe_spending.evals.golden.sql_rules import ALLOWED_VIEWS, check_reference_sql

__all__ = [
    "ALLOWED_VIEWS",
    "EXPECTED_FILE",
    "GOLDEN_FILE",
    "Behavior",
    "Category",
    "Difficulty",
    "ExpectedAnswers",
    "GoldenQuestion",
    "GoldenSet",
    "ResultTable",
    "build_expected",
    "check_reference_sql",
    "load_golden_set",
    "matches",
    "read_expected",
    "to_table",
    "write_expected",
]
