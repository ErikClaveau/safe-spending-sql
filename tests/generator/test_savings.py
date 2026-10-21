"""The savings account and the transfers between a user's own accounts (generator design 5.1 and 5.4):
each transfer is two movements of equal amount on the user's two accounts, the savings balance never
goes below zero, and everything follows the history the user really has."""

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

import pytest

from gen_helpers import REFERENCE, build
from safe_spending.clock import FixedClock
from safe_spending.generator.config import load_config, load_catalog
from safe_spending.generator.dates import next_business_day
from safe_spending.generator.enums import TxCode
from safe_spending.generator.profile import build_profile
from safe_spending.generator.enums import Stage
from safe_spending.generator.rng import stream
from safe_spending.generator.savings import build_savings_plan, savings_capacity_cents
from safe_spending.generator.simulate import generate

N_USERS = 25
ROUNDING = Decimal(25)


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
def everyone_saves(config, catalog):
    """The same population in which every user who can afford it has a savings account."""
    settings = config.savings.model_copy(update={"account_probability": 1.0})
    return generate(config.model_copy(update={"savings": settings}), catalog, FixedClock(REFERENCE))


def savings_account(user_id):
    return user_id * 10 + 2


def current_account(user_id):
    return user_id * 10 + 1


def legs(dataset, user_id=None):
    return [t for t in dataset.transactions if t.counterparty_account_id is not None and user_id in (None, t.user_id)]


def users_with_savings(dataset):
    return sorted({a.user_id for a in dataset.accounts if a.account_id == savings_account(a.user_id)})


def savings_balances(dataset, user_id):
    """[(transaction, balance after it)] on the savings account, deposits before returns on a day."""
    rows = sorted(
        (t for t in dataset.transactions if t.account_id == savings_account(user_id)),
        key=lambda t: (t.booking_date, -t.amount_eur),
    )
    balance, result = Decimal(0), []
    for t in rows:
        balance += t.amount_eur
        result.append((t, balance))
    return result


# ---------------------------------------------------------------------------
# Who has a savings account
# ---------------------------------------------------------------------------


def test_some_users_have_a_savings_account_and_some_do_not(dataset):
    savers = users_with_savings(dataset)
    assert 5 < len(savers) < N_USERS - 5
    assert Counter(a.user_id for a in dataset.accounts).most_common(1)[0][1] == 2  # never more than two


def test_only_users_who_have_a_savings_account_move_money_to_it(dataset):
    assert sorted({t.user_id for t in legs(dataset)}) == users_with_savings(dataset)


def test_only_users_who_can_afford_to_save_get_an_account(dataset, config, catalog):
    minimum = round(config.savings.min_capacity_eur * 100)
    for user_id in users_with_savings(dataset):
        assert savings_capacity_cents(config, build_profile(config, catalog, user_id)) >= minimum


def test_nobody_gets_an_account_if_nobody_can_afford_to_save(config, catalog):
    settings = config.savings.model_copy(update={"account_probability": 1.0, "min_capacity_eur": 100_000})
    population = generate(config.model_copy(update={"savings": settings, "n_users": 8}), catalog, FixedClock(REFERENCE))
    assert not legs(population) and len(population.accounts) == 8


def test_a_user_who_cannot_save_is_skipped_even_if_everyone_wants_an_account(config, catalog):
    # The gate is not binding for the 25 users above, so look for real users it does stop.
    wants_one = config.savings.model_copy(update={"account_probability": 1.0})
    minimum = round(config.savings.min_capacity_eur * 100)
    profiles = (build_profile(config, catalog, user_id) for user_id in range(1, 101))
    poor = [p for p in profiles if savings_capacity_cents(config, p) < minimum]
    assert poor  # some of the 100 users cannot afford to save
    for profile in poor:
        rng = stream(seed=config.seed, user_id=profile.user_id, stage=Stage.SAVINGS)
        assert build_savings_plan(config.model_copy(update={"savings": wants_one}), profile, rng) is None

def test_the_savings_account_is_a_valid_euro_account_of_the_user(dataset):
    savings = [a for a in dataset.accounts if a.account_id == savings_account(a.user_id)]
    current = {a.user_id: a for a in dataset.accounts if a.account_id == current_account(a.user_id)}
    assert savings and all(a.currency == "EUR" and a.iban != current[a.user_id].iban for a in savings)


# ---------------------------------------------------------------------------
# A transfer is two movements
# ---------------------------------------------------------------------------


def transfers(dataset):
    """{(user, day, amount): [the movements]}: each transfer is a pair of legs."""
    grouped = defaultdict(list)
    for t in legs(dataset):
        grouped[(t.user_id, t.booking_date, abs(t.amount_eur))].append(t)
    return grouped


def test_every_transfer_has_exactly_two_movements(dataset):
    grouped = transfers(dataset)
    assert grouped
    assert all(len(pair) == 2 for pair in grouped.values())


def test_the_two_movements_have_equal_amounts_and_opposite_signs(dataset):
    for pair in transfers(dataset).values():
        out, incoming = sorted(pair, key=lambda t: t.amount_eur)
        assert out.tx_code == TxCode.TRANSFER_OUT and incoming.tx_code == TxCode.TRANSFER_IN
        assert out.amount_eur < 0 < incoming.amount_eur
        assert out.amount_eur + incoming.amount_eur == 0  # equal amounts, opposite signs
        assert out.amount == out.amount_eur and out.currency == "EUR" and out.exchange_rate is None


def test_each_movement_is_on_one_account_and_points_to_the_other(dataset):
    for pair in transfers(dataset).values():
        first, second = pair
        assert first.user_id == second.user_id
        assert first.account_id == second.counterparty_account_id
        assert second.account_id == first.counterparty_account_id
        assert {first.account_id, second.account_id} == {current_account(first.user_id), savings_account(first.user_id)}
        assert first.booking_date == first.value_date == second.booking_date == second.value_date


def test_a_transfer_is_filed_as_internal_and_names_no_one(dataset):
    internal = next(c.category_id for c in dataset.categories if c.name == "Traspasos entre cuentas propias")
    for t in legs(dataset):
        assert t.category_id == internal
        assert t.merchant_id is None and t.counterparty is None


def test_the_statement_says_where_the_money_goes_or_comes_from(dataset):
    for t in legs(dataset):
        savings = t.account_id == savings_account(t.user_id)
        other = "CORRIENTE" if savings else "AHORRO"
        direction = "A" if t.tx_code == TxCode.TRANSFER_OUT else "DE"
        assert t.description_raw == f"TRASPASO {direction} CUENTA {other}"


def test_no_movement_that_is_not_a_transfer_points_to_an_account(dataset):
    for t in dataset.transactions:
        assert (t.counterparty_account_id is not None) == (t.description_raw.startswith("TRASPASO "))


# ---------------------------------------------------------------------------
# The monthly deposit
# ---------------------------------------------------------------------------


def deposits(dataset, user_id):
    return [t for t in dataset.transactions if t.account_id == savings_account(user_id) and t.amount_eur > 0
            and t.counterparty_account_id == current_account(user_id)]


def test_the_deposit_is_the_same_whole_amount_every_month(dataset):
    for user_id in users_with_savings(dataset):
        amounts = {t.amount_eur for t in deposits(dataset, user_id)}
        assert len(amounts) == 1
        (amount,) = amounts
        assert amount >= 50 and amount % ROUNDING == 0, (user_id, amount)


def test_the_deposit_never_exceeds_what_the_user_can_save(dataset, config, catalog):
    for user_id in users_with_savings(dataset):
        capacity = Decimal(savings_capacity_cents(config, build_profile(config, catalog, user_id))) / 100
        assert deposits(dataset, user_id)[0].amount_eur <= capacity


def test_there_is_one_deposit_a_few_days_after_each_monthly_pay(dataset):
    for user_id in users_with_savings(dataset):
        pays = [t.booking_date for t in dataset.transactions
                if t.user_id == user_id and t.tx_code == TxCode.SALARY and not t.description_raw.endswith("PAGA EXTRA")]
        made = sorted(t.booking_date for t in deposits(dataset, user_id))
        assert made and len(made) <= len(pays)
        for day in made:
            # 1 to 3 days after the pay, moved to a business day: up to 5 days when it lands on a weekend.
            assert any(timedelta(days=1) <= day - pay <= timedelta(days=5) for pay in pays), (user_id, day)
            assert day == next_business_day(day)


def test_extra_pays_do_not_trigger_a_deposit(dataset):
    short_history = {3}  # the recent sign-up user has fewer pays; the rest have the whole period
    for user_id in users_with_savings(dataset):
        if user_id in short_history:
            continue
        # 24 monthly pays in the period (the last one may be too close to "today" for its deposit),
        # plus four extra pays that must not add deposits: 23 or 24, never 27 or 28.
        assert len(deposits(dataset, user_id)) in (23, 24), user_id

# ---------------------------------------------------------------------------
# The savings balance
# ---------------------------------------------------------------------------


def test_the_savings_balance_never_goes_below_zero(dataset):
    for user_id in users_with_savings(dataset):
        assert all(balance >= 0 for _, balance in savings_balances(dataset, user_id)), user_id


def test_money_comes_back_now_and_then_and_only_from_a_big_enough_balance(dataset, config):
    returns_seen = 0
    for user_id in users_with_savings(dataset):
        before = Decimal(0)
        for t, balance in savings_balances(dataset, user_id):
            if t.amount_eur < 0:  # a return
                returns_seen += 1
                assert before >= config.savings.min_return_eur
                assert -t.amount_eur % ROUNDING == 0 and -t.amount_eur <= before
            before = balance
    assert returns_seen > 0


def test_returns_are_much_rarer_than_deposits(dataset):
    all_legs = [t for t in legs(dataset) if t.account_id == savings_account(t.user_id)]
    returns = [t for t in all_legs if t.amount_eur < 0]
    assert 0 < len(returns) < 0.25 * len(all_legs)


# ---------------------------------------------------------------------------
# The history the user really has
# ---------------------------------------------------------------------------


def test_a_recent_user_with_savings_has_nothing_before_the_signup_date(everyone_saves):
    user = next(u for u in everyone_saves.users if u.user_id == 3)
    mine = legs(everyone_saves, 3)
    assert mine, "user 3 (recent sign-up) must have savings in this population"
    assert min(t.booking_date for t in mine) >= user.signup_date
    assert all(balance >= 0 for _, balance in savings_balances(everyone_saves, 3))


def test_the_recent_users_first_deposit_follows_their_first_pay(everyone_saves):
    pays = sorted(t.booking_date for t in everyone_saves.transactions if t.user_id == 3 and t.tx_code == TxCode.SALARY)
    first_deposit = min(t.booking_date for t in deposits(everyone_saves, 3))
    assert pays and first_deposit > pays[0]
    assert len(pays) - 1 <= len(deposits(everyone_saves, 3)) <= len(pays)  # the last deposit may fall after "today"


def test_a_user_who_already_has_savings_keeps_exactly_the_same_transfers_if_others_get_one(dataset, everyone_saves):
    for user_id in users_with_savings(dataset):
        mine = lambda ds: [(t.booking_date, t.tx_code, t.amount_eur) for t in legs(ds, user_id)]
        assert mine(dataset) == mine(everyone_saves), user_id


def test_having_a_savings_account_does_not_change_any_other_movement(dataset, config, catalog):
    none = config.savings.model_copy(update={"account_probability": 0.0})
    without = generate(config.model_copy(update={"savings": none}), catalog, FixedClock(REFERENCE))
    assert not legs(without) and len(without.accounts) == N_USERS
    key = lambda t: (t.user_id, t.booking_date, t.tx_code, t.amount_eur, t.merchant_id, t.category_id, t.description_raw)
    ordinary = lambda ds: Counter(map(key, (t for t in ds.transactions if t.counterparty_account_id is None)))
    assert ordinary(dataset) == ordinary(without)


def test_savings_do_not_depend_on_the_population_size(dataset):
    _, _, larger = build(N_USERS + 5)
    assert [t for t in legs(larger) if t.user_id <= N_USERS] == legs(dataset)
