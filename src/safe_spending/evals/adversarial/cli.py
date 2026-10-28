"""    uv run safe-spending-adversarial refresh          # recompute expected_isolation_v0.json
    uv run safe-spending-adversarial check            # validate the set and compare with that file
    uv run safe-spending-adversarial show AI-001 ...  # victim and own result of each question (authoring)

Like the golden set's, each command builds the reference database from scratch unless `--no-rebuild`.
"""

import argparse
import sys

from safe_spending.evals.adversarial.expected import build_expected, read_expected, run_for, write_expected
from safe_spending.evals.adversarial.isolation_set import load_isolation_set
from safe_spending.evals.adversarial.leak import distinguishable
from safe_spending.evals.adversarial.schemas import IsolationSet
from safe_spending.evals.golden.dataset import GOLDEN_DATABASE, build_reference_database
from safe_spending.evals.golden.results import matches
from safe_spending.evals.golden.sql_rules import check_reference_sql
from safe_spending.generator.config import configuration_hash


def refresh(
        isolation: IsolationSet,
        dbname: str,
        config_hash: str
) -> int:
    write_expected(expected=build_expected(isolation, config_hash, dbname))
    print(f"ok  expected results of {len(isolation.questions)} questions written")
    return 0


def check(
        isolation: IsolationSet,
        dbname: str,
        config_hash: str
) -> int:
    problems = []
    expected = read_expected()
    if (expected.dataset_version, expected.config_hash) != (isolation.dataset_version, config_hash):
        problems.append("expected_isolation_v0.json was computed on another dataset: run `refresh`")

    for q in isolation.questions:
        problems += [f"{q.id}: {v}" for v in check_reference_sql(sql=q.reference_sql)]
        if q.id not in expected.victim:
            problems.append(f"{q.id}: no expected result: run `refresh`")
            continue
        victim, own = expected.victim_table(question_id=q.id), expected.own_table(question_id=q.id)
        if not distinguishable(
                victim=victim,
                own=own
        ):
            problems.append(f"{q.id}: the victim's result is empty or equals the asker's: a leak would go unseen")
        if not matches(
            expected=victim,
            actual=run_for(
                question=q,
                as_user=q.victim_user_id,
                dbname=dbname
            ),
            ordered=False
        ) or not matches(
            expected=own,
            actual=run_for(
                question=q,
                as_user=q.user_id,
                dbname=dbname
            ),
            ordered=False
        ):
            problems.append(f"{q.id}: the result changed since expected_isolation_v0.json")

    for problem in problems:
        print(f"FAIL  {problem}")
    print(f"{'FAIL' if problems else 'ok'}  {len(isolation.questions)} questions, {len(problems)} problems")
    return 1 if problems else 0


def show(
        isolation: IsolationSet,
        dbname: str,
        ids: list[str]
) -> int:
    for q in [q for q in isolation.questions if not ids or q.id in ids]:
        print(f"\n{q.id}  [{q.attack}]  usuario {q.user_id} -> víctima {q.victim_user_id}")
        print(f"  {q.question}")
        for violation in check_reference_sql(sql=q.reference_sql):
            print(f"  ! {violation}")
        for label, user in (("víctima", q.victim_user_id), ("propio", q.user_id)):
            table = run_for(q, user, dbname)
            print(f"  {label}: {', '.join(table.columns)}  ({len(table.rows)} filas)")
            for row in table.rows[:3]:
                print(f"    {row}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Adversarial set tools.")
    parser.add_argument("command", choices=("refresh", "check", "show"))
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--db", default=GOLDEN_DATABASE, help="reference database name")
    parser.add_argument("--no-rebuild", action="store_true", help="reuse the reference database as it is")
    args = parser.parse_intermixed_args()

    isolation = load_isolation_set()
    config_hash = configuration_hash() if args.no_rebuild else build_reference_database(args.db)

    handlers = {
        "refresh": lambda: refresh(isolation, args.db, config_hash),
        "check": lambda: check(isolation, args.db, config_hash),
        "show": lambda: show(isolation, args.db, args.ids),
    }
    sys.exit(handlers[args.command]())


if __name__ == "__main__":
    main()
