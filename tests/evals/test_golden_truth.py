"""The expected answers checked against the truth by a route that does not use the views (design 6.3).

Two independent sources: the scripted scenarios' `params`, which hold the ground truth by
construction, and the raw generated movements, summed in Python. If one of them disagrees with
what a reference SQL returns over the semantic views, the semantic layer (or the SQL) is wrong,
not the assistant.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from safe_spending.generator.enums import TxCode
from safe_spending.generator.scenarios.amazon_refunds_params import AmazonRefundsParams, RefundKind
from safe_spending.generator.scenarios.anomalous_month_params import AnomalousMonthParams
from safe_spending.generator.scenarios.job_change_params import JobChangeParams
from safe_spending.generator.scenarios.london_trip_params import LondonTripParams
from safe_spending.generator.scenarios.recent_signup_params import RecentSignupParams
from safe_spending.generator.scenarios.subscription_changes_params import SubscriptionChangesParams
from safe_spending.generator.scenarios.zero_category_params import ZeroCategoryParams

MODELS = {
    "subscription_changes": SubscriptionChangesParams,
    "job_change": JobChangeParams,
    "recent_signup": RecentSignupParams,
    "zero_category": ZeroCategoryParams,
    "anomalous_month": AnomalousMonthParams,
    "london_trip": LondonTripParams,
    "amazon_refunds": AmazonRefundsParams,
}
REFERENCE = date(2026, 9, 15)


@pytest.fixture(scope="module")
def params(dataset):
    return {row.type: MODELS[row.type].model_validate_json(row.params) for row in dataset.scenarios}


def cell(results, question_id, row=0, column=0):
    return results[question_id].rows[row][column]


def money(results, question_id, row=0, column=0):
    return Decimal(cell(results, question_id, row, column))


# ---------------------------------------------------------------------------
# Scenario truth (scenarios.params)
# ---------------------------------------------------------------------------


def test_subscriptions_active_today_are_the_baseline_ones_plus_the_new_and_the_raised(results, params, dataset):
    truth = params["subscription_changes"]
    scenario_by_tx = {l.tx_id: l.scenario_id for l in dataset.tx_labels}
    names = {m.merchant_id: m.normalized_name for m in dataset.merchants}
    cutoff = REFERENCE - timedelta(days=35)
    baseline_active = {
        names[t.merchant_id]
        for t in dataset.transactions
        if t.user_id == 1 and scenario_by_tx[t.tx_id] is None and t.booking_date >= cutoff
        and t.merchant_id is not None and "COMPRA TARJ." in t.description_raw
        and names[t.merchant_id] in {"HBO MAX", "ICLOUD", "NETFLIX", "DISNEY PLUS", "BASIC-FIT", "SPOTIFY", "AMAZON PRIME"}
    }
    found = {row[0] for row in results["GS-045"].rows}
    assert found == baseline_active | {truth.started.merchant, truth.price_increase.merchant}
    assert truth.cancelled.merchant not in found


def test_the_price_rise_is_found_with_its_old_price_new_price_and_date(results, params):
    truth = params["subscription_changes"].price_increase
    old, new = results["GS-046"].rows
    assert (Decimal(old[0]), Decimal(new[0])) == (truth.old_eur, truth.new_eur)
    assert new[1] == truth.first_charge_at_new_price.isoformat()


def test_the_cancellation_and_the_start_dates_are_found(results, params):
    truth = params["subscription_changes"]
    assert cell(results, "GS-047") == truth.cancelled.last_charge.isoformat()
    assert cell(results, "GS-048") == truth.started.first_charge.isoformat()


def test_the_job_change_is_found_with_both_employers_amounts_and_the_date(results, params):
    truth = params["job_change"]
    old, new = results["GS-052"].rows
    assert (old[0], Decimal(old[3])) == (truth.old_employer, truth.old_instalment_eur)
    assert (new[0], Decimal(new[3])) == (truth.new_employer, truth.new_instalment_eur)
    assert new[1] == truth.change_date.isoformat()
    assert results["GS-086"].rows[0][:2] == (format(truth.new_instalment_eur, "f"), truth.new_employer)


def test_the_year_of_pay_adds_each_payment_with_its_own_amount(results, params, dataset):
    truth = params["job_change"]
    pays = [t for t in dataset.transactions if t.user_id == 2 and t.tx_code == TxCode.SALARY and t.booking_date.year == 2026]
    assert money(results, "GS-087") == sum(t.amount_eur for t in pays)
    assert {t.amount_eur for t in pays} == {truth.old_instalment_eur, truth.new_instalment_eur}


def test_the_london_trip_totals_match_the_scenario(results, params):
    truth = params["london_trip"]
    assert money(results, "GS-053") == truth.total_charged_eur
    assert money(results, "GS-054") == truth.total_gbp
    assert money(results, "GS-055") == truth.total_fees_eur
    assert cell(results, "GS-057") == truth.n_purchases
    top = max(truth.by_category_eur, key=truth.by_category_eur.get)
    assert results["GS-056"].rows[0] == (top, format(truth.by_category_eur[top], "f"))
    assert money(results, "GS-058") == (truth.total_gbp / truth.total_eur).quantize(Decimal("0.0001"))


def test_the_amazon_figures_match_the_scenario(results, params):
    truth = params["amazon_refunds"]
    assert money(results, "GS-059") == truth.net_eur
    assert money(results, "GS-060") == truth.refunded_eur
    assert cell(results, "GS-061") == truth.n_total_refunds


def test_the_refund_that_crosses_the_month_is_the_scripted_one(results, params):
    crossing = [p for p in params["amazon_refunds"].purchases if p.crosses_month]
    assert len(crossing) == 1 and crossing[0].kind == RefundKind.TOTAL
    row = results["GS-062"].rows
    assert len(row) == 1
    assert row[0] == (crossing[0].refund_date.isoformat(), format(crossing[0].refund_eur, "f"), crossing[0].date.isoformat())


def test_the_anomalous_month_shows_up_as_the_most_expensive_month_and_purchase(results, params):
    truth = params["anomalous_month"]
    assert results["GS-072"].rows[0][0] == truth.month
    assert results["GS-071"].rows[0] == (
        truth.electronics.date.isoformat(), truth.electronics.merchant, format(truth.electronics.amount_eur, "f"))
    assert money(results, "GS-090") >= truth.electronics.amount_eur
    assert truth.extra_by_category_eur["Electrónica"] == truth.electronics.amount_eur


def test_the_zero_category_is_the_one_the_questions_ask_about(results, params):
    truth = params["zero_category"]
    assert truth.category == "Cuidado personal" and truth.purchases_removed > 0
    assert results["GS-011"].rows == (("0",),) and results["GS-012"].rows == (("0",),)
    assert money(results, "GS-089") > 0  # the group still has spending: only the category is zero


def test_the_recent_user_has_history_only_from_the_signup_date(results, params):
    truth = params["recent_signup"]
    first = date.fromisoformat(cell(results, "GS-073"))
    assert truth.signup_date <= first < truth.signup_date + timedelta(days=7)
    assert cell(results, "GS-078") == 0  # nothing in 2025: no data, which is not the same as 0 EUR
    assert money(results, "GS-088") > 0


def test_the_recurring_questions_of_week_five_match_the_scenarios(results, params):
    subscriptions = params["subscription_changes"]
    job = params["job_change"]
    assert money(results, "GS-106") == subscriptions.price_increase.new_eur - subscriptions.price_increase.old_eur
    assert cell(results, "GS-109") == job.old_employer
    assert results["GS-110"].rows[0] == (job.new_employer, job.change_date.isoformat())


def test_the_recent_user_pays_the_phone_from_the_signup_date(results, params):
    first = date.fromisoformat(cell(results, "GS-111"))
    assert params["recent_signup"].signup_date <= first < params["recent_signup"].signup_date + timedelta(days=60)


# ---------------------------------------------------------------------------
# Truth from the raw generated movements, summed in Python
# ---------------------------------------------------------------------------


def spending(dataset, user_id, start=date(2000, 1, 1), end=date(2100, 1, 1)):
    """Net spending: every outflow and refund that is not a move between the user's own accounts."""
    inflows = (TxCode.SALARY, TxCode.TRANSFER_IN, TxCode.BIZUM_IN)
    return -sum(
        t.amount_eur
        for t in dataset.transactions
        if t.user_id == user_id and t.counterparty_account_id is None and t.tx_code not in inflows
        and start <= t.booking_date < end
    )


def income(dataset, user_id, start, end):
    return sum(
        t.amount_eur
        for t in dataset.transactions
        if t.user_id == user_id and t.counterparty_account_id is None
        and t.tx_code in (TxCode.SALARY, TxCode.TRANSFER_IN, TxCode.BIZUM_IN) and start <= t.booking_date < end
    )


def test_spending_questions_match_the_raw_movements(results, dataset):
    assert money(results, "GS-003") == spending(dataset, 10, date(2026, 8, 1), date(2026, 9, 1))
    assert money(results, "GS-009") == spending(dataset, 12, date(2026, 9, 1))
    assert money(results, "GS-070") == spending(dataset, 15, date(2026, 1, 1))


def test_the_savings_question_matches_income_minus_spending(results, dataset):
    start, end = date(2025, 1, 1), date(2026, 1, 1)
    saved = [Decimal(row[1]) for row in results["GS-037"].rows]
    assert len(saved) == 12
    assert sum(saved) == income(dataset, 8, start, end) - spending(dataset, 8, start, end)
    assert money(results, "GS-038") == income(dataset, 9, start, end) - spending(dataset, 9, start, end)


def test_rent_and_pay_questions_match_the_raw_movements(results, dataset):
    rent = {c.name: c.category_id for c in dataset.categories}["Alquiler"]
    paid = sum(-t.amount_eur for t in dataset.transactions
               if t.user_id == 12 and t.category_id == rent and t.booking_date.year == 2025)
    assert money(results, "GS-005") == paid
    pay = sum(t.amount_eur for t in dataset.transactions
              if t.user_id == 10 and t.tx_code == TxCode.SALARY and t.booking_date.year == 2026)
    assert money(results, "GS-039") == pay


def test_the_refunds_total_matches_the_raw_refunds(results, dataset):
    refunds = sum(t.amount_eur for t in dataset.transactions if t.user_id == 1 and t.tx_code == TxCode.CARD_REFUND)
    assert refunds > 0 and money(results, "GS-063") == refunds


def test_the_transfers_questions_match_the_raw_internal_legs(results, dataset):
    to_savings = sum(
        -t.amount_eur for t in dataset.transactions
        if t.user_id == 10 and t.counterparty_account_id is not None and t.account_id == 10 * 10 + 1
        and t.amount_eur < 0 and t.booking_date.year == 2025
    )
    assert money(results, "GS-066") == to_savings > 0
    balance = sum(t.amount_eur for t in dataset.transactions if t.account_id == 11 * 10 + 2)
    assert money(results, "GS-067", column=1) == balance > 0
    returns = [t for t in dataset.transactions if t.user_id == 12 and t.account_id == 12 * 10 + 2 and t.amount_eur < 0]
    assert cell(results, "GS-068") == len(returns) >= 1
    monthly = [Decimal(row[1]) for row in results["GS-069"].rows]
    assert sum(monthly) == sum(
        -t.amount_eur for t in dataset.transactions
        if t.user_id == 14 and t.account_id == 14 * 10 + 1 and t.counterparty_account_id is not None
        and t.amount_eur < 0 and t.booking_date.year == 2026
    )


def test_transfers_are_not_counted_as_spending_in_the_question_that_traps_it(results, dataset):
    start = date(2026, 1, 1)
    naive = -sum(t.amount_eur for t in dataset.transactions
                 if t.user_id == 15 and t.amount_eur < 0 and t.booking_date >= start)  # counts the transfers too
    assert money(results, "GS-070") == spending(dataset, 15, start) < naive


def merchant_total(dataset, user_id, merchant, start=date(2000, 1, 1), end=date(2100, 1, 1)):
    ids = {m.merchant_id for m in dataset.merchants if m.normalized_name == merchant}
    return -sum(
        t.amount_eur
        for t in dataset.transactions
        if t.user_id == user_id and t.merchant_id in ids and start <= t.booking_date < end
    )


def test_recurring_merchant_totals_match_the_raw_movements(results, dataset):
    assert money(results, "GS-094") == merchant_total(dataset, 4, "ENDESA", date(2025, 1, 1), date(2026, 1, 1))
    assert money(results, "GS-096") == merchant_total(dataset, 1, "LYCAMOBILE", date(2026, 1, 1), date(2027, 1, 1))
    assert money(results, "GS-105") == merchant_total(dataset, 1, "SPOTIFY")
    assert money(results, "GS-114") == merchant_total(dataset, 9, "BASIC-FIT", date(2026, 1, 1), date(2027, 1, 1))


def test_the_number_of_pays_matches_the_raw_movements(results, dataset):
    pays = [t for t in dataset.transactions if t.user_id == 2 and t.tx_code is TxCode.SALARY]
    assert cell(results, "GS-108") == len(pays)


def purchases(dataset, user_id, merchants, start, end, over=Decimal(0)):
    """Amounts spent (positive) at those merchants in the period, one per purchase, refunds left out."""
    ids = {m.merchant_id for m in dataset.merchants if m.normalized_name in merchants}
    return [
        -t.amount_eur
        for t in dataset.transactions
        if t.user_id == user_id and t.merchant_id in ids and start <= t.booking_date < end
        and t.amount_eur < 0 and -t.amount_eur > over
    ]


def test_compound_filter_questions_match_the_raw_movements(results, dataset):
    year_2026 = (date(2026, 1, 1), date(2027, 1, 1))
    zara_pull = purchases(dataset, 14, {"ZARA", "PULL&BEAR"}, *year_2026, over=Decimal(50))
    assert money(results, "GS-121") == sum(zara_pull)
    assert cell(results, "GS-122") == len(purchases(dataset, 8, {"STARBUCKS"}, *year_2026, over=Decimal(5)))
    assert money(results, "GS-123") == sum(purchases(dataset, 10, {"AMAZON", "EL CORTE INGLES"}, *year_2026))
    assert money(results, "GS-130") == sum(purchases(dataset, 2, {"TICKETMASTER", "YELMO"}, date(2025, 1, 1), date(2026, 1, 1)))


def test_income_and_savings_questions_match_the_raw_movements(results, dataset):
    year_2025 = (date(2025, 1, 1), date(2026, 1, 1))
    assert money(results, "GS-134") == income(dataset, 11, *year_2025)
    assert money(results, "GS-135") == income(dataset, 12, *year_2025) - spending(dataset, 12, *year_2025)
    assert money(results, "GS-136") == income(dataset, 13, date(2026, 8, 1), date(2026, 9, 1)) - spending(
        dataset, 13, date(2026, 8, 1), date(2026, 9, 1))
    assert money(results, "GS-141") == (spending(dataset, 10, *year_2025) / 12).quantize(Decimal("0.01"))
    assert money(results, "GS-152") == income(dataset, 10, date(2026, 1, 1), date(2026, 9, 1))


def test_the_recent_user_has_spent_more_than_they_have_earned(results, dataset):
    everything = (date(2000, 1, 1), date(2100, 1, 1))
    assert money(results, "GS-143") == income(dataset, 3, *everything) - spending(dataset, 3, *everything)
    assert money(results, "GS-143") < 0


def test_the_february_pay_is_late_so_february_has_no_income(results, dataset):
    assert income(dataset, 6, date(2026, 2, 1), date(2026, 3, 1)) == 0
    assert income(dataset, 6, date(2026, 3, 1), date(2026, 4, 1)) == 2 * Decimal("2500.00")
    assert cell(results, "GS-147") == "0"
