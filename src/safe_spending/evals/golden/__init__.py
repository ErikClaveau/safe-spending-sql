"""The golden set: questions about the evaluation users, each with the SQL that answers it."""

from safe_spending.evals.golden.enums import Behavior, Category, Difficulty, Split
from safe_spending.evals.golden.expected import ExpectedAnswers, build_expected, read_expected, write_expected
from safe_spending.evals.golden.golden_set import EXPECTED_FILE, GOLDEN_FILE, GoldenSet, load_golden_set
from safe_spending.evals.golden.question import GoldenQuestion
from safe_spending.evals.golden.results import ResultTable, matches, matches_allowing_extra_columns, to_table
from safe_spending.evals.golden.splits import derive_test_ids, load_test_ids, split_of
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
    "Split",
    "build_expected",
    "check_reference_sql",
    "derive_test_ids",
    "load_golden_set",
    "load_test_ids",
    "matches",
    "matches_allowing_extra_columns",
    "read_expected",
    "split_of",
    "to_table",
    "write_expected",
]
