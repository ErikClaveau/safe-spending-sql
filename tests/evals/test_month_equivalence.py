"""A month written as '2026-03' and as its first day '2026-03-01' is the same answer; nothing else is."""

import pytest

from safe_spending.evals.golden import ResultTable, matches, matches_allowing_extra_columns


def table(*rows):
    return ResultTable(columns=tuple(f"c{i}" for i in range(len(rows[0]))), rows=tuple(rows))


def test_a_month_and_its_first_day_match_in_both_directions():
    assert matches(table(("2026-03", "10.00")), table(("2026-03-01", "10.00")), ordered=False)
    assert matches(table(("2026-03-01", "10.00")), table(("2026-03", "10.00")), ordered=False)


def test_it_works_with_the_extra_column_comparison_too():
    expected = table(("2026-01", "400.00"), ("2026-03", "800.00"))
    actual = table(("2026-01-01", "ES**7343", "400.00"), ("2026-03-01", "ES**7343", "800.00"))

    assert matches_allowing_extra_columns(expected, actual, ordered=False)


@pytest.mark.parametrize("other", ["2026-03-02", "2026-03-15", "2026-04-01", "2025-03-01"])
def test_another_day_or_another_month_is_not_the_same(other):
    assert not matches(table(("2026-03", "1")), table((other, "1")), ordered=False)


def test_a_real_date_is_never_taken_for_a_month():
    assert not matches(table(("2026-03-15", "1")), table(("2026-03-01", "1")), ordered=False)
    assert not matches(table(("2026-03-01", "1")), table(("2026-03-01-extra", "1")), ordered=False)


def test_the_amount_must_still_match():
    assert not matches(table(("2026-03", "10.00")), table(("2026-03-01", "11.00")), ordered=False)
