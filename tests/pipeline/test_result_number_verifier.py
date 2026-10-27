"""`ResultNumberVerifier`: an answer's numbers must come from the result (or the question, the SQL, today)."""

from datetime import date
from decimal import Decimal

import pytest

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.verification import ResultNumberVerifier

TODAY = date(2026, 9, 15)
QUESTION = "¿Cuánto gasté en los últimos 3 meses?"
SQL = "SELECT SUM(importe_eur) FROM v_gastos WHERE fecha >= '2026-06-15' LIMIT 28"

RESULT = QueryResult(
    columns=("fecha", "importe_eur", "concepto"),
    rows=(
        (date(2026, 3, 4), Decimal("-1234.56"), "COMPRA TARJ. MERCADONA"),
        (date(2026, 3, 5), Decimal("-12.50"), "BIZUM RECIBO 4521 CNR999A1B2"),
    ),
    truncated=False,
)


def verify(answer, result=RESULT, *, question=QUESTION, sql=SQL, assumptions=None):
    return ResultNumberVerifier().verify(
        answer, result, question=question, sql=sql, assumptions=assumptions, today=TODAY
    )


@pytest.mark.parametrize("answer", [
    "Has gastado 1.234,56 € el 4 de marzo de 2026.",
    "Fueron 12,50 € y 12,5 € (mismo valor).",
    "Pagaste 1.234,56 € y luego 12,50 €.",
    "En los últimos 3 meses no hay nada nuevo.",         # from the question
    "Desde el 15 de junio de 2026 hasta hoy, 15 de septiembre.",  # SQL literal and today
    "El concepto decía RECIBO 4521.",                    # digits a concept carries
    "No tienes movimientos que cumplan eso.",
])
def test_numbers_that_come_from_a_source_are_traced(answer):
    verification = verify(answer)

    assert verification.ok, verification.untraced


@pytest.mark.parametrize("answer, untraced", [
    ("Has tenido 28 nóminas.", ("28",)),                  # a count the model made, and only LIMIT has it
    ("Son 4 movimientos.", ("4",)),
    ("En total 1.247,06 €.", ("1.247,06",)),             # a sum
    ("Gastaste 1.235 € aprox.", ("1.235",)),             # a rounding
    ("Gastaste 12,51 €.", ("12,51",)),
])
def test_numbers_the_model_worked_out_are_untraced(answer, untraced):
    verification = verify(answer)

    assert verification.untraced == untraced
    assert not verification.ok


@pytest.mark.parametrize("answer", [
    "El 4 de marzo de 2026 y el 5 de marzo.",
    "Fechas: 2026-03-04 y 05/03/2026.",
    "En marzo de 2026 gastaste 12,50 €.",
    "Hoy, 15 de septiembre de 2026.",
    "Desde el 15 de junio.",                              # a date of the SQL
])
def test_dates_are_checked_by_day_and_year_against_the_dates_the_data_has(answer):
    assert verify(answer).ok


@pytest.mark.parametrize("answer, untraced", [
    ("El 9 de marzo de 2026.", ("9",)),                   # 9 is a month of today, not a day anywhere
    ("El 4 de marzo de 2025.", ("2025",)),
    ("El 04/03/2027.", ("2027",)),
])
def test_a_date_the_data_does_not_have_is_untraced(answer, untraced):
    assert verify(answer).untraced == untraced


def test_a_bare_year_is_traced_by_the_years_of_the_dates():
    assert verify("Entre 2025 y 2026 hay datos.").untraced == ("2025",)  # no date of 2025 in the data
    assert verify("Hay movimientos de marzo y de 2026.").ok


def test_the_parts_of_a_date_do_not_license_a_count():
    """A row on the 4th must not make "4 movimientos" pass."""
    assert verify("Son 4 movimientos el 4 de marzo.").untraced == ("4",)


def test_the_sign_is_not_part_of_the_number():
    assert verify("Has gastado 12,50 € y tienes -12,50 € en la cuenta.").ok


def test_a_zero_result_can_be_said_as_zero():
    empty = QueryResult(columns=("total",), rows=((Decimal("0.00"),),), truncated=False)

    assert verify("Has gastado 0,00 €.", empty).ok


def test_a_code_in_a_concept_is_not_a_number():
    verification = verify("El Bizum traía el código CNR999A1B2.")

    assert verification.checked == () and verification.ok


def test_numbered_list_markers_are_not_numbers():
    answer = "Tus movimientos:\n1. Mercadona: 1.234,56 €\n2) Bizum: 12,50 €"

    verification = verify(answer)

    assert verification.ok
    assert verification.checked == ("1.234,56", "12,50")


def test_every_row_counts_as_a_source_even_those_the_model_was_not_shown():
    rows = tuple((Decimal(i),) for i in range(100, 160))

    assert verify("Una cifra: 159.", QueryResult(columns=("n",), rows=rows, truncated=False)).ok


def test_paging_in_the_sql_is_not_a_source():
    assert verify("Salen 28 filas.", sql="SELECT 1 FROM v_gastos LIMIT 28").untraced == ("28",)
