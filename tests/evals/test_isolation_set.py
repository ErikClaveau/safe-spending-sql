"""The isolation set: well formed, runnable under RLS, and its expected file up to date."""

import pytest

from safe_spending.db.query import run_as_user
from safe_spending.evals.adversarial import (
    Attack,
    distinguishable,
    leaked,
    load_isolation_set,
    read_expected,
)
from safe_spending.evals.golden import ALLOWED_VIEWS, load_golden_set, matches, to_table
from safe_spending.evals.golden.sql_rules import check_reference_sql

MIN_QUESTIONS = 20


@pytest.fixture(scope="module")
def isolation():
    return load_isolation_set()


@pytest.fixture(scope="module")
def expected():
    return read_expected()


def test_ids_are_contiguous_and_every_attack_is_covered(isolation):
    ids = [q.id for q in isolation.questions]

    assert ids == [f"AI-{n:03d}" for n in range(1, len(ids) + 1)]
    assert len(ids) >= MIN_QUESTIONS
    assert {q.attack for q in isolation.questions} == set(Attack)


def test_the_set_is_pinned_to_the_golden_datasets_version(isolation):
    golden = load_golden_set()

    assert (isolation.dataset_version, isolation.reference_date) == (golden.dataset_version, golden.reference_date)


def test_askers_are_users_without_a_scenario(isolation):
    assert {q.user_id for q in isolation.questions} <= set(range(8, 16))


def test_reference_sql_obeys_the_assistants_own_rules(isolation):
    for q in isolation.questions:
        assert not check_reference_sql(q.reference_sql), q.id
    assert ALLOWED_VIEWS  # the rules above are the ones that allow only the semantic views


def test_a_leak_of_every_question_could_be_seen(isolation, expected):
    """If the victim had no data, or the same as the asker, a leak would pass for a normal answer."""
    for q in isolation.questions:
        assert distinguishable(expected.victim_table(q.id), expected.own_table(q.id)), q.id


def test_the_detector_sees_a_leak_in_every_question(isolation, expected):
    for q in isolation.questions:
        victim, own = expected.victim_table(q.id), expected.own_table(q.id)
        assert leaked(actual=victim, victim=victim, own=own), q.id
        assert not leaked(actual=own, victim=victim, own=own), q.id


def test_expected_results_are_those_of_the_reference_database(isolation, expected, reference_db):
    assert expected.dataset_version == isolation.dataset_version
    for q in isolation.questions:
        as_victim = to_table(run_as_user(q.victim_user_id, q.reference_sql, dbname=reference_db))
        as_asker = to_table(run_as_user(q.user_id, q.reference_sql, dbname=reference_db))

        assert matches(expected.victim_table(q.id), as_victim, ordered=False), q.id
        assert matches(expected.own_table(q.id), as_asker, ordered=False), q.id


def test_asking_as_the_asker_never_returns_the_victims_data(isolation, expected, reference_db):
    """The property the whole set protects, checked on the real schema: RLS answers with the asker's rows."""
    for q in isolation.questions:
        actual = to_table(run_as_user(q.user_id, q.reference_sql, dbname=reference_db))

        assert not leaked(
            actual=actual,
            victim=expected.victim_table(q.id),
            own=expected.own_table(q.id)
        ), q.id
