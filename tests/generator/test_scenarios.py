"""Scripted scenarios (generator design 5.5): the ground truth in `scenarios.params` must match
what is actually in the generated movements, and a scenario must not touch anything else."""

import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from statistics import median

import pytest
from pydantic import ValidationError

from gen_helpers import REFERENCE, build
from safe_spending.clock import FixedClock
from safe_spending.generator import text
from safe_spending.generator.config import GeneratorConfig, load_config
from safe_spending.generator.enums import ScenarioType, TxCode
from safe_spending.generator.scenarios.anomalous_month_params import AnomalousMonthParams
from safe_spending.generator.scenarios.job_change_params import JobChangeParams
from safe_spending.generator.scenarios.recent_signup_params import RecentSignupParams
from safe_spending.generator.scenarios.subscription_changes_params import SubscriptionChangesParams
from safe_spending.generator.scenarios.zero_category_params import ZeroCategoryParams
from safe_spending.generator.simulate import generate

SCENARIO_USERS = {
    1: ScenarioType.SUBSCRIPTION_CHANGES,
    2: ScenarioType.JOB_CHANGE,
    3: ScenarioType.RECENT_SIGNUP,
    4: ScenarioType.ZERO_CATEGORY,
    5: ScenarioType.ANOMALOUS_MONTH,
}
N_USERS = 8  # users 1-5 have a scenario; 6-8 are plain


@pytest.fixture(scope="module")
def built():
    return build(N_USERS)


@pytest.fixture(scope="module")
def config(built):
    return built[0]


@pytest.fixture(scope="module")
def catalog(built):
    return built[1]


@pytest.fixture(scope="module")
def dataset(built):
    return built[2]


@pytest.fixture(scope="module")
def baseline(config, catalog):
    """The same population without any scenario."""
    return generate(config.model_copy(update={"scenarios": ()}), catalog, FixedClock(REFERENCE))


def params_of(dataset, user_id, model):
    row = next(s for s in dataset.scenarios if s.user_id == user_id)
    return model.model_validate_json(row.params)


def transactions_of(dataset, user_id, *, tagged=None):
    scenario_by_tx = {l.tx_id: l.scenario_id for l in dataset.tx_labels}
    return [
        t
        for t in dataset.transactions
        if t.user_id == user_id and (tagged is None or (scenario_by_tx[t.tx_id] is not None) == tagged)
    ]


def fingerprints(transactions):
    """What identifies a movement ignoring ids and descriptions (those depend on neighbours)."""
    return Counter((t.booking_date, t.tx_code, t.amount_eur, t.merchant_id, t.category_id) for t in transactions)


def merchant_names(dataset):
    return {m.merchant_id: m.normalized_name for m in dataset.merchants}


def category_names(dataset):
    return {c.category_id: c.name for c in dataset.categories}


# ---------------------------------------------------------------------------
# Configuration: the user -> scenario map is fixed and validated
# ---------------------------------------------------------------------------


def test_the_scenario_map_is_fixed_in_the_config(config):
    assert {a.user_id: a.type for a in config.scenarios} == SCENARIO_USERS


def with_scenarios(config, scenarios) -> GeneratorConfig:
    return GeneratorConfig.model_validate({**config.model_dump(), "scenarios": scenarios})


def test_a_scenario_outside_the_functional_split_is_rejected(config):
    with pytest.raises(ValidationError, match="outside the eval_functional split"):
        with_scenarios(config, [{"user_id": 30, "type": "job_change"}])
    with pytest.raises(ValidationError, match="outside the eval_functional split"):
        with_scenarios(config, [{"user_id": 17, "type": "job_change"}])


def test_assigning_the_same_scenario_twice_to_a_user_is_rejected(config):
    twice = [{"user_id": 1, "type": "job_change"}, {"user_id": 1, "type": "job_change"}]
    with pytest.raises(ValidationError, match="assigned twice"):
        with_scenarios(config, twice)


def test_an_unknown_scenario_type_is_rejected(config):
    with pytest.raises(ValidationError):
        with_scenarios(config, [{"user_id": 1, "type": "moon_landing"}])


# ---------------------------------------------------------------------------
# The scenarios table and the labels
# ---------------------------------------------------------------------------


def test_there_is_one_scenario_row_per_assignment(dataset):
    assert {s.user_id: s.type for s in dataset.scenarios} == SCENARIO_USERS
    ids = [s.scenario_id for s in dataset.scenarios]
    assert len(ids) == len(set(ids))
    for row in dataset.scenarios:
        assert row.scenario_id == f"{row.user_id:03d}-{row.type}"
        assert row.description
        assert isinstance(json.loads(row.params), dict)


def test_only_the_scenario_users_have_tagged_movements(dataset):
    scenario_by_tx = {l.tx_id: l.scenario_id for l in dataset.tx_labels}
    owner = {t.tx_id: t.user_id for t in dataset.transactions}
    known = {s.scenario_id: s.user_id for s in dataset.scenarios}
    for tx_id, scenario_id in scenario_by_tx.items():
        if scenario_id is not None:
            assert known[scenario_id] == owner[tx_id]
    # Sign-up and zero-category only remove movements, so they tag nothing.
    tagged_users = {owner[tx_id] for tx_id, sid in scenario_by_tx.items() if sid is not None}
    assert tagged_users == {1, 2, 5}


def test_users_without_a_scenario_are_untouched_by_the_scenarios(dataset, baseline):
    for user_id in range(6, N_USERS + 1):
        assert transactions_of(dataset, user_id) == transactions_of(baseline, user_id)


def test_scenario_rows_do_not_depend_on_the_population_size():
    _, _, small = build(2)
    _, _, large = build(6)
    assert [s for s in large.scenarios if s.user_id <= 2] == small.scenarios


# ---------------------------------------------------------------------------
# Subscription changes (user 1): one starts, one raises its price, one is cancelled
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def subscriptions(dataset):
    params = params_of(dataset, 1, SubscriptionChangesParams)
    by_merchant = defaultdict(list)
    names = merchant_names(dataset)
    for t in transactions_of(dataset, 1, tagged=True):
        by_merchant[names[t.merchant_id]].append(t)
    return params, {name: sorted(rows, key=lambda t: t.booking_date) for name, rows in by_merchant.items()}


def month_keys(rows):
    return [(t.booking_date.year, t.booking_date.month) for t in rows]


def test_the_three_subscriptions_are_new_to_the_user(subscriptions, dataset, baseline, catalog):
    params, charges = subscriptions
    chosen = {params.started.merchant, params.price_increase.merchant, params.cancelled.merchant}
    assert len(chosen) == 3 and set(charges) == chosen
    subscribed = {
        merchant_names(baseline)[t.merchant_id]
        for t in transactions_of(baseline, 1)
        if t.merchant_id in {m.merchant_id for m in catalog.merchants if m.channel == "subscription"}
    }
    assert subscribed.isdisjoint(chosen)


def test_a_started_subscription_charges_monthly_from_its_first_charge(subscriptions):
    params, charges = subscriptions
    rows = charges[params.started.merchant]
    assert rows[0].booking_date == params.started.first_charge
    assert {-t.amount_eur for t in rows} == {params.started.monthly_eur}
    assert len(set(month_keys(rows))) == len(rows)  # one charge per month
    assert len({t.booking_date.day for t in rows}) == 1
    assert (REFERENCE - params.started.first_charge).days > 90  # it has history to compare


def test_a_price_increase_splits_the_charges_in_two_prices(subscriptions):
    params, charges = subscriptions
    rows = charges[params.price_increase.merchant]
    change = params.price_increase
    assert change.new_eur > change.old_eur
    assert {-t.amount_eur for t in rows if t.booking_date < change.first_charge_at_new_price} == {change.old_eur}
    assert {-t.amount_eur for t in rows if t.booking_date >= change.first_charge_at_new_price} == {change.new_eur}
    assert any(t.booking_date < change.first_charge_at_new_price for t in rows)
    assert len(set(month_keys(rows))) == len(rows)
    assert len({t.booking_date.day for t in rows}) == 1


def test_a_cancelled_subscription_stops_charging(subscriptions):
    params, charges = subscriptions
    rows = charges[params.cancelled.merchant]
    assert rows[-1].booking_date == params.cancelled.last_charge
    assert {-t.amount_eur for t in rows} == {params.cancelled.monthly_eur}
    assert (REFERENCE - params.cancelled.last_charge).days > 90  # clearly gone, not just a late bill


def test_subscription_changes_only_add_movements(dataset, baseline):
    untagged = fingerprints(transactions_of(dataset, 1, tagged=False))
    assert untagged == fingerprints(transactions_of(baseline, 1))


# ---------------------------------------------------------------------------
# Job change (user 2): another employer and a higher salary from some pay on
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def salaries(dataset):
    params = params_of(dataset, 2, JobChangeParams)
    rows = sorted(
        (t for t in transactions_of(dataset, 2) if t.tx_code == TxCode.SALARY),
        key=lambda t: (t.booking_date, t.tx_id),
    )
    return params, rows


def test_the_salary_changes_employer_and_amount_at_the_change_date(salaries):
    params, rows = salaries
    before = [t for t in rows if t.booking_date < params.change_date]
    after = [t for t in rows if t.booking_date >= params.change_date]
    assert before and len(after) >= 6
    assert {t.counterparty for t in before} == {params.old_employer}
    assert {t.counterparty for t in after} == {params.new_employer}
    assert {t.amount_eur for t in before} == {params.old_instalment_eur}
    assert {t.amount_eur for t in after} == {params.new_instalment_eur}
    assert params.old_employer != params.new_employer


def test_the_new_salary_is_a_raise_of_a_plausible_size(salaries):
    params, _ = salaries
    ratio = params.new_instalment_eur / params.old_instalment_eur
    assert Decimal("1.10") <= ratio <= Decimal("1.36")


def test_a_job_change_keeps_the_number_of_pays(salaries, baseline):
    _, rows = salaries
    assert len(rows) == 28
    assert len(rows) == sum(1 for t in transactions_of(baseline, 2) if t.tx_code == TxCode.SALARY)


def test_salary_descriptions_follow_the_employer(salaries):
    params, rows = salaries
    for t in rows:
        employer = params.new_employer if t.booking_date >= params.change_date else params.old_employer
        assert t.description_raw.startswith(text.statement(f"NOMINA {employer}", 70)[:40])


def test_only_the_rewritten_pays_are_tagged(dataset, salaries):
    params, _ = salaries
    tagged = transactions_of(dataset, 2, tagged=True)
    assert tagged and all(t.tx_code == TxCode.SALARY and t.booking_date >= params.change_date for t in tagged)


def test_a_job_change_leaves_everything_but_the_salary_untouched(dataset, baseline):
    other = lambda ds: fingerprints(t for t in transactions_of(ds, 2) if t.tx_code != TxCode.SALARY)
    assert other(dataset) == other(baseline)


# ---------------------------------------------------------------------------
# Recent sign-up (user 3): only a few months of history
# ---------------------------------------------------------------------------


def test_a_recent_user_has_no_movement_before_the_signup_date(dataset):
    params = params_of(dataset, 3, RecentSignupParams)
    user = next(u for u in dataset.users if u.user_id == 3)
    rows = transactions_of(dataset, 3)
    assert user.signup_date == params.signup_date
    assert params.history_days == (REFERENCE - params.signup_date).days
    assert 60 <= params.history_days <= 100
    assert rows and min(t.booking_date for t in rows) >= params.signup_date


def test_a_recent_user_keeps_the_movements_after_the_signup_date(dataset, baseline):
    params = params_of(dataset, 3, RecentSignupParams)
    expected = fingerprints(t for t in transactions_of(baseline, 3) if t.booking_date >= params.signup_date)
    assert fingerprints(transactions_of(dataset, 3)) == expected
    assert 2 <= sum(1 for t in transactions_of(dataset, 3) if t.tx_code == TxCode.SALARY) <= 4


def test_every_other_user_signs_up_at_the_start_of_the_period(dataset, config):
    for user in dataset.users:
        if user.user_id != 3:
            assert user.signup_date == config.period_start


# ---------------------------------------------------------------------------
# Category at zero (user 4)
# ---------------------------------------------------------------------------


def test_a_zero_category_user_never_spends_in_it(dataset, baseline, catalog):
    params = params_of(dataset, 4, ZeroCategoryParams)
    category = catalog.category(params.category)
    assert params.group == category.group_name
    assert all(t.category_id != category.category_id for t in transactions_of(dataset, 4))


def test_the_zero_is_a_real_zero_and_not_a_lack_of_data(dataset, baseline, catalog):
    params = params_of(dataset, 4, ZeroCategoryParams)
    category_id = catalog.category(params.category).category_id
    in_baseline = [t for t in transactions_of(baseline, 4) if t.category_id == category_id]
    assert params.purchases_removed == len(in_baseline) > 0
    assert len(transactions_of(dataset, 4)) == len(transactions_of(baseline, 4)) - len(in_baseline)


def test_a_zero_category_user_keeps_every_other_movement(dataset, baseline, catalog):
    params = params_of(dataset, 4, ZeroCategoryParams)
    category_id = catalog.category(params.category).category_id
    expected = fingerprints(t for t in transactions_of(baseline, 4) if t.category_id != category_id)
    assert fingerprints(transactions_of(dataset, 4)) == expected


# ---------------------------------------------------------------------------
# Anomalous month (user 5)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def anomaly(dataset):
    params = params_of(dataset, 5, AnomalousMonthParams)
    year, month = (int(part) for part in params.month.split("-"))
    return params, (year, month), transactions_of(dataset, 5, tagged=True)


def test_the_anomalous_month_is_a_complete_month(anomaly):
    _, (year, month), _ = anomaly
    assert date(year, month, 1) < date(2026, 9, 1)
    assert date(year, month, 1) >= date(2024, 10, 1)


def test_everything_added_happens_inside_the_anomalous_month(anomaly):
    _, month, tagged = anomaly
    assert tagged and {(t.booking_date.year, t.booking_date.month) for t in tagged} == {month}


def test_the_extra_spend_matches_what_was_added(dataset, anomaly):
    params, _, tagged = anomaly
    names = category_names(dataset)
    by_category = defaultdict(Decimal)
    for t in tagged:
        by_category[names[t.category_id]] -= t.amount_eur
    assert dict(sorted(by_category.items())) == params.extra_by_category_eur
    assert sum(by_category.values()) == params.extra_total_eur
    assert set(by_category) == {"Electrónica", "Viajes y alojamiento", "Restaurantes y bares"}


def test_the_big_electronics_purchase_is_in_the_data(dataset, anomaly):
    params, _, tagged = anomaly
    names = merchant_names(dataset)
    purchase = [t for t in tagged if names.get(t.merchant_id) == params.electronics.merchant
                and t.booking_date == params.electronics.date]
    assert [-t.amount_eur for t in purchase] == [params.electronics.amount_eur]
    assert 900 <= params.electronics.amount_eur <= 1800


def test_the_anomalous_month_really_stands_out(dataset, anomaly):
    _, (year, month), _ = anomaly
    spend = defaultdict(Decimal)
    for t in transactions_of(dataset, 5):
        if t.amount_eur < 0:
            spend[(t.booking_date.year, t.booking_date.month)] -= t.amount_eur
    complete = [key for key in spend if key not in {(2024, 9), (2026, 9)}]  # first and last are partial
    typical = median(spend[key] for key in complete if key != (year, month))
    assert spend[(year, month)] > Decimal("1.4") * typical


def test_an_anomalous_month_only_adds_movements(dataset, baseline):
    untagged = fingerprints(transactions_of(dataset, 5, tagged=False))
    assert untagged == fingerprints(transactions_of(baseline, 5))
