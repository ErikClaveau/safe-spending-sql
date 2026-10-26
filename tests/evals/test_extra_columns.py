"""`matches_allowing_extra_columns`: extra columns are forgiven, wrong answers are not."""

from safe_spending.evals.golden import ResultTable, matches, matches_allowing_extra_columns


def table(*rows, width=None):
    width = width or len(rows[0])
    return ResultTable(columns=tuple(f"c{i}" for i in range(width)), rows=tuple(rows))


EXPECTED = table(("985.50", "839.34"))


def test_an_extra_column_is_forgiven_where_the_strict_comparison_is_not():
    actual = table(("985.50", "839.34", "146.16"))

    assert not matches(EXPECTED, actual, ordered=False)
    assert matches_allowing_extra_columns(EXPECTED, actual, ordered=False)


def test_the_requested_columns_may_come_in_another_position_or_order():
    assert matches_allowing_extra_columns(EXPECTED, table(("146.16", "839.34", "985.50")), ordered=False)


def test_a_wrong_value_in_a_requested_column_is_still_wrong():
    assert not matches_allowing_extra_columns(EXPECTED, table(("985.50", "1.00", "146.16")), ordered=False)


def test_missing_columns_are_still_wrong():
    assert not matches_allowing_extra_columns(table(("1", "2", "3")), table(("1", "2")), ordered=False)


def test_a_different_number_of_rows_is_still_wrong_whatever_the_extras():
    expected = table(("a", "1"), ("b", "2"))

    assert not matches_allowing_extra_columns(expected, table(("a", "1", "x")), ordered=False)


def test_columns_are_matched_together_so_rows_cannot_be_mixed():
    expected = table(("a", "1"), ("b", "2"))
    # Each column has the right values on its own, but they are paired wrongly
    actual = table(("a", "2", "x"), ("b", "1", "y"))

    assert not matches_allowing_extra_columns(expected, actual, ordered=False)


def test_order_still_matters_when_the_question_says_so():
    expected = table(("a", "1"), ("b", "2"))
    actual = table(("b", "2", "x"), ("a", "1", "y"))

    assert matches_allowing_extra_columns(expected, actual, ordered=False)
    assert not matches_allowing_extra_columns(expected, actual, ordered=True)


def test_an_empty_result_with_extra_columns_matches_an_empty_expected():
    assert matches_allowing_extra_columns(table(width=2), table(width=3), ordered=False)


def test_an_absurd_number_of_extra_columns_is_not_searched():
    wide = table(tuple(str(i) for i in range(30)))

    assert not matches_allowing_extra_columns(table(("0", "1", "2", "3", "4")), wide, ordered=False)


def test_the_same_columns_in_another_order_are_right_leniently_and_wrong_strictly():
    expected = table(("1777.98", "1391.28"))
    actual = table(("1391.28", "1777.98"))

    assert not matches(expected, actual, ordered=False)
    assert matches_allowing_extra_columns(expected, actual, ordered=False)


def test_reordering_columns_never_mixes_the_rows():
    expected = table(("a", "1"), ("b", "2"))

    assert matches_allowing_extra_columns(expected, table(("1", "a"), ("2", "b")), ordered=False)
    assert not matches_allowing_extra_columns(expected, table(("2", "a"), ("1", "b")), ordered=False)
