"""What each isolation question returns for the victim and for the asker, kept in a file.

Generated (`safe-spending-adversarial refresh`), never edited by hand, like the golden set's. A leak is
recognised by comparing with these tables, so a data change that alters them must be a visible decision.
"""

import json
from pathlib import Path

from safe_spending.db.query import run_as_user
from safe_spending.evals.adversarial.isolation_set import EXPECTED_FILE
from safe_spending.evals.adversarial.schemas import ExpectedLeaks, IsolationQuestion, IsolationSet
from safe_spending.evals.golden import ResultTable, to_table


def run_for(
        question: IsolationQuestion,
        as_user: int,
        dbname: str
) -> ResultTable:
    return to_table(run_as_user(as_user, question.reference_sql, dbname=dbname))


def build_expected(
        isolation: IsolationSet,
        config_hash: str,
        dbname: str
) -> ExpectedLeaks:
    return ExpectedLeaks(
        dataset_version=isolation.dataset_version,
        config_hash=config_hash,
        victim={q.id: run_for(q, q.victim_user_id, dbname).to_json() for q in isolation.questions},
        own={q.id: run_for(q, q.user_id, dbname).to_json() for q in isolation.questions},
    )


def write_expected(
        expected: ExpectedLeaks,
        path: Path = EXPECTED_FILE
) -> None:
    """One line per question, so a change shows as one changed line."""
    dump = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False)

    def block(name: str, tables: dict[str, dict]) -> str:
        lines = [f"    {dump(i)}: {dump(tables[i])}" for i in sorted(tables)]
        return f"  {dump(name)}: {{\n" + ",\n".join(lines) + "\n  }"

    text = (
        "{\n"
        f"  \"config_hash\": {dump(expected.config_hash)},\n"
        f"  \"dataset_version\": {dump(expected.dataset_version)},\n"
        f"{block('own', expected.own)},\n"
        f"{block('victim', expected.victim)}\n"
        "}\n"
    )
    path.write_text(text, encoding="utf-8")


def read_expected(path: Path = EXPECTED_FILE) -> ExpectedLeaks:
    return ExpectedLeaks.model_validate_json(path.read_text(encoding="utf-8"))
