"""    uv run safe-spending-golden refresh          # recompute expected_v0.json on the reference database
    uv run safe-spending-golden check            # validate the set and compare with expected_v0.json
    uv run safe-spending-golden show GS-001 ...  # run questions and print their results (authoring)

Each command builds the reference database from scratch (a few seconds) unless `--no-rebuild`
is given, so the answers never depend on what is loaded in the development database.
"""

import argparse
import sys
from pathlib import Path

from safe_spending.db.query import run_as_user
from safe_spending.evals.golden.dataset import GOLDEN_DATABASE, build_reference_database
from safe_spending.evals.golden.expected import build_expected, read_expected, write_expected
from safe_spending.evals.golden.golden_set import EXPECTED_FILE, GoldenSet, load_golden_set
from safe_spending.evals.golden.question import GoldenQuestion
from safe_spending.evals.golden.results import ResultTable, matches, to_table
from safe_spending.evals.golden.sql_rules import check_reference_sql


def run_question(
        question: GoldenQuestion,
        dbname: str
) -> ResultTable:
    return to_table(run_as_user(question.user_id, question.reference_sql, dbname=dbname))


def refresh(
        golden: GoldenSet,
        dbname: str,
        config_hash: str,
        path: Path = EXPECTED_FILE
) -> int:
    tables = {q.id: run_question(q, dbname) for q in golden.answerable}
    write_expected(build_expected(golden, config_hash, tables), path)
    print(f"ok  expected answers of {len(tables)} questions written to {path}")
    return 0


def check(
        golden: GoldenSet,
        dbname: str,
        config_hash: str
) -> int:
    problems = []
    expected = read_expected()
    if (expected.dataset_version, expected.config_hash) != (golden.dataset_version, config_hash):
        problems.append("expected_v0.json was computed on another dataset: run `refresh`")

    for question in golden.answerable:
        for violation in check_reference_sql(question.reference_sql):
            problems.append(f"{question.id}: {violation}")
        actual = run_question(question, dbname)
        if question.id not in expected.answers:
            problems.append(f"{question.id}: no expected answer: run `refresh`")
        elif not matches(expected.table(question.id), actual, ordered=question.ordered):
            problems.append(f"{question.id}: the result changed since expected_v0.json")

    for problem in problems:
        print(f"FAIL  {problem}")
    print(f"{'FAIL' if problems else 'ok'}  {len(golden.questions)} questions, {len(problems)} problems")
    return 1 if problems else 0


def show(
        golden: GoldenSet,
        dbname: str,
        ids: list[str]
) -> int:
    questions = [golden.question_by_id(i) for i in ids] if ids else list(golden.answerable)
    for question in questions:
        print(f"\n{question.id}  [{question.category}/{question.difficulty}]  usuario {question.user_id}")
        print(f"  {question.question}")
        if not question.reference_sql:
            print(f"  (sin SQL: {question.behavior})")
            continue
        for violation in check_reference_sql(question.reference_sql):
            print(f"  ! {violation}")
        table = run_question(question, dbname)
        print(f"  columnas: {', '.join(table.columns)}  ({len(table.rows)} filas)")
        for row in table.rows[:8]:
            print(f"    {row}")
        if len(table.rows) > 8:
            print(f"    ... {len(table.rows) - 8} más")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden set tools.")
    parser.add_argument("command", choices=("refresh", "check", "show"))
    parser.add_argument("ids", nargs="*", help="question ids for `show` (all answerable ones if omitted)")
    parser.add_argument("--db", default=GOLDEN_DATABASE, help="reference database name")
    parser.add_argument("--no-rebuild", action="store_true", help="reuse the reference database as it is")
    args = parser.parse_intermixed_args()

    golden = load_golden_set()
    config_hash = None
    if not args.no_rebuild:
        config_hash = build_reference_database(args.db)
    else:
        from safe_spending.generator.config import configuration_hash

        config_hash = configuration_hash()

    handlers = {
        "refresh": lambda: refresh(golden, args.db, config_hash),
        "check": lambda: check(golden, args.db, config_hash),
        "show": lambda: show(golden, args.db, args.ids),
    }
    sys.exit(handlers[args.command]())


if __name__ == "__main__":
    main()
