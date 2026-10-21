"""Event stages: recurring payments and random purchases (design 5.2)."""

import math
from datetime import date, timedelta

import numpy as np

from safe_spending.generator.config import Catalog, GeneratorConfig, Merchant
from safe_spending.generator.enums import Channel, TxCode, UtilityKind
from safe_spending.generator.dates import MONTHS_PER_YEAR, day_in_month, months, next_business_day
from safe_spending.generator.events.calendar import Calendar
from safe_spending.generator.events.event import Event
from safe_spending.generator.money import CENTS_PER_EUR, to_cents
from safe_spending.generator.profile import Profile
from safe_spending.generator.profile.utility import Utility

DAYS_PER_MONTH = 30.4375
MIN_PURCHASE_CENTS = 50

PAYS_PER_YEAR = 14
EXTRA_PAY_MONTHS = (6, 12)  # 14 instalments: two extra pays, June and December
EXTRA_PAY_NOTE = "extra"

# Category names as they appear in categories.yaml.
SALARY_CATEGORY = "Nómina"
RENT_CATEGORY = "Alquiler"

# Electricity bills peak in winter: base * (1 + amplitude * cos(...)), plus lognormal noise.
ELECTRICITY_SEASONAL_AMPLITUDE = 0.3
ELECTRICITY_NOISE_SIGMA = 0.06

NEUTRAL_SEASON = (1.0,) * MONTHS_PER_YEAR
MAX_ONLINE_BOOKING_DELAY_DAYS = 1  # only card-present purchases can take longer to book


def recurring_events(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        rng: np.random.Generator,
        end: date
) -> list[Event]:
    """Salary (14 pays), rent, direct-debit utilities and card subscriptions."""
    start = config.period_start
    events = []

    for year, month in months(start, end):
        events += _salary_events(
            catalog=catalog,
            profile=profile,
            year=year,
            month=month
        )
        events.append(
            _rent_event(
                catalog=catalog,
                profile=profile,
                year=year,
                month=month
            )
        )
        events += _utility_events(
            catalog=catalog,
            profile=profile,
            rng=rng,
            year=year,
            month=month
        )
        events += _subscription_events(
            catalog=catalog,
            profile=profile,
            year=year,
            month=month
        )

    return [
        e
        for e in events
        if start <= e.booking_date <= end
    ]


def purchase_events(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        rng: np.random.Generator,
        end: date
) -> list[Event]:
    """Card purchases: income -> monthly budget by category -> Poisson events that consume it."""
    calendar = Calendar.between(
        start=config.period_start,
        end=end
    )
    weekday_factor = _unit_mean(weights=config.weekday_weights)
    delay_p = _unit_sum(weights=config.card_delay_weights)
    events = []

    for category_name in sorted(profile.habitual):
        events += _category_purchases(
            config=config,
            catalog=catalog,
            profile=profile,
            rng=rng,
            end=end,
            category_name=category_name,
            calendar=calendar,
            weekday_factor=weekday_factor,
            delay_p=delay_p
        )

    return events


def _salary_events(
        catalog: Catalog,
        profile: Profile,
        year: int,
        month: int
) -> list[Event]:
    pay_date = next_business_day(
        day=day_in_month(
            year=year,
            month=month,
            day=profile.pay_day
        )
    )
    category_id = catalog.category(SALARY_CATEGORY).category_id
    salary_cents = round(profile.annual_net_cents / PAYS_PER_YEAR)
    salary = _event(
        day=pay_date,
        tx_code=TxCode.SALARY,
        amount_cents=salary_cents,
        category_id=category_id,
        counterparty=profile.employer
    )
    events = [salary]

    if month in EXTRA_PAY_MONTHS:
        events.append(salary.model_copy(update={"note": EXTRA_PAY_NOTE}))

    return events


def _rent_event(
        catalog: Catalog,
        profile: Profile,
        year: int,
        month: int
) -> Event:
    return _event(
        day=next_business_day(
            day=day_in_month(
                year=year,
                month=month,
                day=profile.rent_day
            )
        ),
        tx_code=TxCode.TRANSFER_OUT,
        amount_cents=-profile.rent_cents,
        category_id=catalog.category(RENT_CATEGORY).category_id,
        counterparty=profile.landlord
    )


def _utility_events(
        catalog: Catalog,
        profile: Profile,
        rng: np.random.Generator,
        year: int,
        month: int
) -> list[Event]:
    return [
        _event(
            day=next_business_day(
                day=day_in_month(
                    year=year,
                    month=month,
                    day=utility.day
                )
            ),
            tx_code=TxCode.DIRECT_DEBIT,
            amount_cents=-_utility_amount_cents(
                utility=utility,
                month=month,
                rng=rng
            ),
            category_id=catalog.category(utility.merchant.category).category_id,
            merchant=utility.merchant,
            counterparty=utility.merchant.legal_name
        )
        for utility in profile.utilities
    ]


def _utility_amount_cents(
        utility: Utility,
        month: int,
        rng: np.random.Generator
) -> int:
    if utility.merchant.kind != UtilityKind.ELECTRICITY:
        return utility.base_cents

    seasonal = 1 + ELECTRICITY_SEASONAL_AMPLITUDE * math.cos(2 * math.pi * (month - 1) / MONTHS_PER_YEAR)
    noise = math.exp(float(rng.normal(0, ELECTRICITY_NOISE_SIGMA)))

    return round(utility.base_cents * seasonal * noise)


def _subscription_events(
        catalog: Catalog,
        profile: Profile,
        year: int,
        month: int
) -> list[Event]:
    return [
        _event(
            day=day_in_month(
                year=year,
                month=month,
                day=subscription.day
            ),
            tx_code=TxCode.CARD_PURCHASE,
            amount_cents=-to_cents(subscription.merchant.price_eur),
            category_id=catalog.category(subscription.merchant.category).category_id,
            merchant=subscription.merchant
        )
        for subscription in profile.subscriptions
    ]


def _category_purchases(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        rng: np.random.Generator,
        end: date,
        category_name: str,
        calendar: Calendar,
        weekday_factor: np.ndarray,
        delay_p: np.ndarray
) -> list[Event]:
    habitual = profile.habitual[category_name]
    merchants = [m for m, _ in habitual]
    shares = np.array([s for _, s in habitual])

    rate = _daily_rate(
        config=config,
        catalog=catalog,
        profile=profile,
        category_name=category_name,
        calendar=calendar,
        weekday_factor=weekday_factor
    )
    counts = rng.poisson(rate)
    total = int(counts.sum())

    if total == 0:
        return []

    day_index = np.repeat(np.arange(len(calendar.days)), counts)
    merchant_index = rng.choice(len(merchants), size=total, p=shares)
    z = rng.standard_normal(total)
    delay = rng.choice(len(delay_p), size=total, p=delay_p)

    category_id = catalog.category(category_name).category_id
    events = []
    for i in range(total):
        merchant = merchants[int(merchant_index[i])]
        operation = calendar.days[int(day_index[i])]
        booking = operation + timedelta(days=_booking_delay_days(
            merchant=merchant,
            delay=int(delay[i])
        ))

        if booking > end:
            continue  # not booked yet at the reference date

        events.append(
            Event(
                booking_date=booking,
                value_date=operation,
                tx_code=TxCode.CARD_PURCHASE,
                amount_cents=-_ticket_cents(merchant, float(z[i])),
                category_id=category_id,
                merchant=merchant
            )
        )

    return events


def _daily_rate(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        category_name: str,
        calendar: Calendar,
        weekday_factor: np.ndarray
) -> np.ndarray:
    """Expected number of purchases per day: monthly budget / mean ticket, shaped by weekday and season."""
    habitual = profile.habitual[category_name]
    mean_ticket = sum(share * m.mean_eur for m, share in habitual)

    group_name = catalog.category(category_name).group_name
    season = _unit_mean(weights=config.seasonality.get(group_name, NEUTRAL_SEASON))

    monthly_income_eur = profile.monthly_income_cents / CENTS_PER_EUR
    archetype = config.archetypes[profile.archetype]
    budget = archetype.category_budget_share[category_name] * monthly_income_eur * profile.budget_noise

    return budget / mean_ticket / DAYS_PER_MONTH * weekday_factor[calendar.weekdays] * season[calendar.month_index]


def _booking_delay_days(
        merchant: Merchant,
        delay: int
) -> int:
    if merchant.channel == Channel.CARD_PRESENT:
        return delay

    return min(delay, MAX_ONLINE_BOOKING_DELAY_DAYS)


def _ticket_cents(
        merchant: Merchant,
        z: float
) -> int:
    return max(MIN_PURCHASE_CENTS, to_cents(merchant.median_eur * math.exp(merchant.sigma * z)))


def _unit_mean(weights) -> np.ndarray:
    """Weights scaled so that their mean is 1."""
    array = np.array(weights, dtype=float)

    return array / array.mean()


def _unit_sum(weights) -> np.ndarray:
    """Weights scaled so that their sum is 1 (probabilities)."""
    array = np.array(weights, dtype=float)

    return array / array.sum()


def _event(
        day: date,
        **fields
) -> Event:
    """A movement whose booking and value dates coincide."""
    return Event(
        booking_date=day,
        value_date=day,
        **fields
    )
