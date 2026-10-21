"""The structure of the golden set: well formed, balanced, and anchored to the right users and scenarios."""

from collections import Counter

import pytest
from pydantic import ValidationError

from safe_spending.evals.golden import Behavior, Category, Difficulty, GoldenQuestion, GoldenSet, load_golden_set
from safe_spending.generator.config import load_config

FUNCTIONAL_USERS = range(1, 16)


def question(**overrides):
    fields = dict(
        id="GS-001", question="¿Cuánto gasté?", user_id=8, category="agregado_simple", difficulty="facil",
        behavior="answer", reference_sql="SELECT 1 LIMIT 1",
    )
    return GoldenQuestion(**{**fields, **overrides})


# ---------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------


def test_the_set_is_the_size_the_plan_asks_for_in_week_two(golden):
    assert 80 <= len(golden.questions) <= 100  # ~80 questions for v0 (plan section 14)


def test_ids_are_contiguous_from_gs_001(golden):
    assert [q.id for q in golden.questions] == [f"GS-{n:03d}" for n in range(1, len(golden.questions) + 1)]


def test_the_set_belongs_to_the_current_dataset(golden):
    config = load_config()
    assert golden.dataset_version == config.dataset_version
    assert golden.reference_date == config.reference_date


def test_no_question_is_asked_twice(golden):
    keys = [(q.user_id, q.question.strip().lower()) for q in golden.questions]
    assert len(keys) == len(set(keys))


def test_every_question_is_in_spanish_and_reads_like_a_question_or_an_order(golden):
    for q in golden.questions:
        assert q.question.strip() and q.question[0] in "¿ABCDEFGHIJKLMNÑOPQRSTUVWXYZ", q.id
        assert q.question.rstrip().endswith(("?", "."))


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_every_category_of_the_plan_is_covered_with_several_questions(golden):
    counts = Counter(q.category for q in golden.questions)
    assert set(counts) == set(Category)
    assert all(n >= 4 for n in counts.values()), counts


def test_difficulty_is_spread_with_most_questions_in_the_middle(golden):
    counts = Counter(q.difficulty for q in golden.questions)
    share = lambda d: counts[d] / len(golden.questions)
    assert set(counts) == set(Difficulty)
    assert 0.15 <= share(Difficulty.FACIL) <= 0.45
    assert 0.35 <= share(Difficulty.MEDIA) <= 0.65
    assert 0.10 <= share(Difficulty.DIFICIL) <= 0.35


def test_all_four_expected_behaviors_are_present(golden):
    counts = Counter(q.behavior for q in golden.questions)
    assert set(counts) == set(Behavior)
    assert counts[Behavior.ANSWER] > 0.7 * len(golden.questions)
    assert all(counts[b] >= 4 for b in (Behavior.CLARIFY, Behavior.NO_DATA, Behavior.REFUSE))


def test_questions_are_asked_as_functional_evaluation_users_only(golden):
    config = load_config()
    for q in golden.questions:
        assert q.user_id in FUNCTIONAL_USERS
        assert config.split_of(q.user_id) == "eval_functional"


def test_every_functional_user_has_several_questions(golden):
    counts = Counter(q.user_id for q in golden.questions)
    assert set(counts) == set(FUNCTIONAL_USERS)
    assert all(n >= 3 for n in counts.values()), counts


def test_the_zero_euros_and_the_no_data_cases_are_both_there(golden):
    answers_with_zero = [q for q in golden.questions if q.category == Category.AGREGADO_SIMPLE and "COALESCE" in (q.reference_sql or "")]
    no_data = [q for q in golden.questions if q.behavior == Behavior.NO_DATA]
    assert len(answers_with_zero) >= 2 and len(no_data) >= 4  # "0 EUR" is not "no data"


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_a_scenario_anchor_names_a_real_scenario_of_the_same_user(golden):
    config = load_config()
    assigned = {f"{a.user_id:03d}-{a.type}": a.user_id for a in config.scenarios}
    anchored = [q for q in golden.questions if q.scenario_id]
    assert anchored
    for q in anchored:
        assert assigned.get(q.scenario_id) == q.user_id, q.id


def test_every_scripted_scenario_has_several_questions(golden):
    config = load_config()
    counts = Counter(q.scenario_id for q in golden.questions if q.scenario_id)
    for assignment in config.scenarios:
        assert counts[f"{assignment.user_id:03d}-{assignment.type}"] >= 2, assignment.type


# ---------------------------------------------------------------------------
# The rules each question must follow
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"id": "GS-1"}, "must look like GS-001"),
        ({"behavior": "clarify", "reference_sql": None}, "expects behavior answer"),
        ({"category": "ambigua"}, "expects behavior clarify"),
        ({"category": "sin_datos"}, "expects behavior no_data"),
        ({"category": "fuera_de_dominio", "behavior": "refuse"}, "has no SQL"),
        ({"reference_sql": None}, "needs a reference_sql"),
        ({"reference_sql": "   "}, "needs a reference_sql"),
        ({"ordered": True}, "needs an ORDER BY"),
    ],
)
def test_an_incoherent_question_is_rejected(overrides, message):
    with pytest.raises(ValidationError, match=message):
        question(**overrides)


def test_a_coherent_question_of_each_behavior_is_accepted():
    question()
    question(category="ambigua", behavior="clarify", reference_sql=None)
    question(category="sin_datos", behavior="no_data")
    question(category="fuera_de_dominio", behavior="refuse", reference_sql=None)
    question(ordered=True, reference_sql="SELECT a FROM v_gastos ORDER BY a LIMIT 1")


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        question(esperado="42")


def test_the_set_rejects_duplicate_or_unordered_ids():
    first, second = question(id="GS-001"), question(id="GS-002", question="Otra pregunta")
    with pytest.raises(ValidationError, match="duplicate"):
        GoldenSet(dataset_version="0", reference_date="2026-09-15", questions=[first, first])
    with pytest.raises(ValidationError, match="id order"):
        GoldenSet(dataset_version="0", reference_date="2026-09-15", questions=[second, first])


def test_the_file_loads_as_a_golden_set():
    assert isinstance(load_golden_set(), GoldenSet)
