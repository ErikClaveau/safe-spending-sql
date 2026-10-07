"""Event stages: recurring payments and random purchases (design 5.2)."""

import math
from datetime import date, timedelta

import numpy as np

from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.enums import TxCode
from safe_spending.generator.dates import daterange, day_in_month, months, next_business_day
from safe_spending.generator.events.event import Event
from safe_spending.generator.money import to_cents
from safe_spending.generator.profile import Profile

DAYS_PER_MONTH = 30.4375
MIN_PURCHASE_CENTS = 50
EXTRA_PAY_MONTHS = (6, 12)  # 14 instalments: two extra pays, June and December


def recurring_events(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        rng: np.random.Generator,
        end: date
) -> list[Event]:
    """Salary (14 pays), rent, direct-debit utilities and card subscriptions."""
    start = config.period_start
    events: list[Event] = []

    def add(day: date, **fields) -> None:
        if start <= day <= end:
            events.append(Event(booking_date=day, value_date=day, **fields))

    salary_cents = round(profile.annual_net_cents / 14)
    category = catalog.category

    for year, month in months(start, end):
        pay_date = next_business_day(day_in_month(year, month, profile.pay_day))
        add(
            pay_date,
            tx_code=TxCode.SALARY,
            amount_cents=salary_cents,
            category_id=category("Nómina").category_id,
            counterparty=profile.employer
        )
        if month in EXTRA_PAY_MONTHS:
            add(
                pay_date,
                tx_code=TxCode.SALARY,
                amount_cents=salary_cents,
                category_id=category("Nómina").category_id,
                counterparty=profile.employer,
                note="extra"
            )

        add(
            next_business_day(day_in_month(year, month, profile.rent_day)),
            tx_code=TxCode.TRANSFER_OUT,
            amount_cents=-profile.rent_cents,
            category_id=category("Alquiler").category_id,
            counterparty=profile.landlord
        )

        for utility in profile.utilities:
            amount = utility.base_cents
            if utility.merchant.kind == "electricity":
                seasonal = 1 + 0.3 * math.cos(2 * math.pi * (month - 1) / 12)  # winter high
                amount = round(utility.base_cents * seasonal * math.exp(float(rng.normal(0, 0.06))))
            add(
                next_business_day(day_in_month(year, month, utility.day)),
                tx_code=TxCode.DIRECT_DEBIT,
                amount_cents=-amount,
                category_id=category(utility.merchant.category).category_id,
                merchant=utility.merchant,
                counterparty=utility.merchant.legal_name
            )

        for subscription in profile.subscriptions:
            merchant = subscription.merchant
            add(
                day_in_month(year, month, subscription.day),
                tx_code=TxCode.CARD_PURCHASE,
                amount_cents=-to_cents(merchant.price_eur),
                category_id=category(merchant.category).category_id,
                merchant=merchant
            )

    return events


def purchase_events(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        rng: np.random.Generator,
        end: date
) -> list[Event]:
    """Card purchases: income -> monthly budget by category -> Poisson events that consume it."""
    days = daterange(config.period_start, end)
    weekdays = np.array([d.weekday() for d in days])
    month_index = np.array([d.month - 1 for d in days])

    weekday_factor = np.array(config.weekday_weights, dtype=float)
    weekday_factor /= weekday_factor.mean()
    delay_p = np.array(config.card_delay_weights, dtype=float)
    delay_p /= delay_p.sum()

    archetype = config.archetypes[profile.archetype]
    monthly_income_eur = profile.monthly_income_cents / 100
    events: list[Event] = []

    for category_name in sorted(profile.habitual):
        habitual = profile.habitual[category_name]
        merchants = [m for m, _ in habitual]
        shares = np.array([s for _, s in habitual])
        mean_ticket = sum(share * m.mean_eur for m, share in habitual)

        season = np.array(config.seasonality.get(catalog.category(category_name).group_name, [1.0] * 12))
        season = season / season.mean()

        budget = archetype.category_budget_share[category_name] * monthly_income_eur * profile.budget_noise
        rate = budget / mean_ticket / DAYS_PER_MONTH * weekday_factor[weekdays] * season[month_index]

        counts = rng.poisson(rate)
        total = int(counts.sum())
        if total == 0:
            continue
        day_index = np.repeat(np.arange(len(days)), counts)
        merchant_index = rng.choice(len(merchants), size=total, p=shares)
        z = rng.standard_normal(total)
        delay = rng.choice(len(delay_p), size=total, p=delay_p)

        category_id = catalog.category(category_name).category_id
        for i in range(total):
            merchant = merchants[int(merchant_index[i])]
            booking_delay = int(delay[i]) if merchant.channel == "card_present" else min(int(delay[i]), 1)
            operation = days[int(day_index[i])]
            booking = operation + timedelta(days=booking_delay)
            if booking > end:
                continue  # not booked yet at the reference date
            cents = max(MIN_PURCHASE_CENTS, to_cents(merchant.median_eur * math.exp(merchant.sigma * float(z[i]))))
            events.append(Event(booking_date=booking, value_date=operation, tx_code=TxCode.CARD_PURCHASE,
                                amount_cents=-cents, category_id=category_id, merchant=merchant))
    return events
