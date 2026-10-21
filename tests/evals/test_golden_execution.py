"""Every reference SQL runs under RLS on the official dataset and returns what expected_v0.json says."""

import pytest

from safe_spending.evals.golden import Behavior, matches, read_expected
from safe_spending.evals.golden.cli import check, refresh
from safe_spending.evals.golden.golden_set import EXPECTED_FILE


def answerable_ids():
    from safe_spending.evals.golden import load_golden_set

    return [q.id for q in load_golden_set().answerable]


@pytest.fixture(scope="module")
def expected():
    return read_expected()


# ---------------------------------------------------------------------------
# They run
# ---------------------------------------------------------------------------


def test_every_reference_sql_runs_and_returns_something(golden, results):
    for q in golden.answerable:
        assert results[q.id].rows, f"{q.id} returned no rows"


def test_a_question_returns_a_small_readable_result(golden, results):
    for q in golden.answerable:
        assert len(results[q.id].rows) <= 50, q.id
        assert 1 <= len(results[q.id].columns) <= 6, q.id


def test_running_a_question_twice_gives_exactly_the_same_result(golden, run, results):
    for q in golden.answerable:
        assert run(q) == results[q.id], q.id


def test_ordered_questions_have_a_total_order(golden, results):
    # With ties the order would depend on the planner: no two rows may be equal on every sort key.
    for q in golden.answerable:
        if q.ordered:
            rows = results[q.id].rows
            assert len(set(rows)) == len(rows), q.id


# ---------------------------------------------------------------------------
# They return what was agreed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("question_id", answerable_ids())
def test_the_result_is_the_expected_one(question_id, golden, results, expected):
    question = golden.question_by_id(question_id)
    assert question_id in expected.answers
    assert matches(expected.table(question_id), results[question_id], ordered=question.ordered), (
        f"{question_id} changed: expected {expected.answers[question_id]['rows']}, got {results[question_id].rows}"
    )


def test_the_expected_file_covers_exactly_the_answerable_questions(golden, expected):
    assert sorted(expected.answers) == sorted(q.id for q in golden.answerable)


def test_the_expected_file_belongs_to_this_dataset_and_configuration(golden, expected, config_hash):
    assert expected.dataset_version == golden.dataset_version
    assert expected.config_hash == config_hash


def test_regenerating_the_expected_file_gives_the_committed_bytes(golden, reference_db, config_hash, tmp_path):
    fresh = tmp_path / "expected.json"
    refresh(golden, reference_db, config_hash, path=fresh)
    assert fresh.read_bytes() == EXPECTED_FILE.read_bytes()


def test_the_check_command_passes_on_the_committed_state(golden, reference_db, config_hash, capsys):
    assert check(golden, reference_db, config_hash) == 0
    assert "0 problems" in capsys.readouterr().out


def test_the_check_command_notices_a_changed_answer(golden, reference_db, config_hash, monkeypatch, capsys):
    from safe_spending.evals.golden import ExpectedAnswers

    real = read_expected()
    tampered = dict(real.answers)
    tampered["GS-001"] = {"columns": ["gasto_total"], "rows": [["1.00"]]}
    monkeypatch.setattr(
        "safe_spending.evals.golden.cli.read_expected",
        lambda: ExpectedAnswers(dataset_version=real.dataset_version, config_hash=real.config_hash, answers=tampered),
    )
    assert check(golden, reference_db, config_hash) == 1
    assert "GS-001: the result changed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# RLS decides who sees what: the SQL has no user filter
# ---------------------------------------------------------------------------


def test_the_same_sql_gives_another_user_their_own_answer_not_the_first_users(golden, run):
    basic_fit = golden.question_by_id("GS-047")  # user 1: last Basic-Fit charge
    assert run(basic_fit).rows[0][0] is not None
    assert run(basic_fit, as_user=2).rows == ((None,),)  # user 2 never paid Basic-Fit: MAX of nothing


def test_an_unrelated_user_does_not_see_a_scenario_users_data(golden, run):
    london = golden.question_by_id("GS-053")  # user 6: the trip to London
    assert run(london).rows[0][0] is not None
    assert run(london, as_user=8).rows == ((None,),)


# ---------------------------------------------------------------------------
# "0 EUR" is not "no data"
# ---------------------------------------------------------------------------


def count_in_period(reference_db, user_id, where):
    from safe_spending.db.query import run_as_user

    return run_as_user(user_id, f"SELECT COUNT(*) FROM v_movimientos WHERE {where} LIMIT 1", dbname=reference_db).rows[0][0]


def test_the_zero_euro_questions_have_data_in_the_period_so_the_zero_is_real(golden, results, reference_db):
    for question_id, where in (
        ("GS-011", "fecha >= '2024-01-01'"),
        ("GS-012", "fecha >= '2025-01-01' AND fecha < '2026-01-01'"),
    ):
        assert results[question_id].rows == (("0",),)
        assert count_in_period(reference_db, golden.question_by_id(question_id).user_id, where) > 100


def test_the_no_data_questions_have_no_movements_in_the_period(golden, results):
    no_data = [q for q in golden.questions if q.behavior == Behavior.NO_DATA]
    assert len(no_data) >= 4
    for q in no_data:
        assert results[q.id].rows == ((0,),), q.id  # zero movements: the period is outside the data
