"""The held-out questions: the file equals the rule, and the rule gives every category a share."""

from collections import Counter

from safe_spending.evals.golden import Split, derive_test_ids, load_test_ids, split_of


def test_the_frozen_file_is_exactly_what_the_rule_derives(golden):
    assert tuple(sorted(load_test_ids())) == derive_test_ids(golden)


def test_test_questions_exist_in_the_golden_set(golden):
    assert load_test_ids() <= {q.id for q in golden.questions}


def test_about_a_third_is_held_out_and_no_category_is_left_without_test_questions(golden):
    test_ids = load_test_ids()
    total = Counter(q.category for q in golden.questions)
    held = Counter(q.category for q in golden.questions if q.id in test_ids)

    assert 0.25 <= len(test_ids) / len(golden.questions) <= 0.35
    assert set(held) == set(total)


def test_split_of_labels_every_question(golden):
    test_ids = load_test_ids()
    labels = Counter(split_of(q.id, test_ids) for q in golden.questions)

    assert labels[Split.TEST] == len(test_ids)
    assert labels[Split.DEV] == len(golden.questions) - len(test_ids)
