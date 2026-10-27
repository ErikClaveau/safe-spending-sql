"""The expected answers: what every reference SQL returns on the dataset, kept in a file.

They are generated, never edited by hand (`safe-spending-golden refresh`). Keeping them in the
repository lets a reviewer read the numbers, and lets a test notice when the dataset, the
generator or the semantic layer change an answer without anyone deciding it should.
"""

import json
from pathlib import Path

from safe_spending.evals.golden.golden_set import EXPECTED_FILE, GoldenSet
from safe_spending.evals.golden.results import ResultTable
from safe_spending.evals.golden.schemas import ExpectedAnswers


def build_expected(
        golden: GoldenSet,
        config_hash: str,
        tables: dict[str, ResultTable]
) -> ExpectedAnswers:
    return ExpectedAnswers(
        dataset_version=golden.dataset_version,
        config_hash=config_hash,
        answers={question_id: tables[question_id].to_json() for question_id in sorted(tables)},
    )


def write_expected(
        expected: ExpectedAnswers,
        path: Path = EXPECTED_FILE
) -> None:
    """One line per question, so the file reads like a table and a change shows as one changed line."""
    dump = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False)
    lines = [f"    {dump(question_id)}: {dump(expected.answers[question_id])}" for question_id in sorted(expected.answers)]
    text = (
        "{\n"
        "  \"answers\": {\n" + ",\n".join(lines) + "\n  },\n"
        f"  \"config_hash\": {dump(expected.config_hash)},\n"
        f"  \"dataset_version\": {dump(expected.dataset_version)}\n"
        "}\n"
    )
    path.write_text(text, encoding="utf-8")


def read_expected(path: Path = EXPECTED_FILE) -> ExpectedAnswers:
    return ExpectedAnswers.model_validate_json(path.read_text(encoding="utf-8"))
