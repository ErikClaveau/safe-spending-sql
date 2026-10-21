"""Transfers between a user's own accounts (design 5.4).

Each month, after the pay, a fixed amount goes from the current account to the savings account.
Now and then a part of the savings balance comes back. Every transfer is two movements, one on
each account, on the same day and for the same amount. The savings balance is tracked, so a
return never takes out more than is there.
"""

from datetime import date, timedelta
from typing import NamedTuple

import numpy as np

from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.dates import day_in_month, months, next_business_day
from safe_spending.generator.enums import AccountKind, TxCode
from safe_spending.generator.events import Event
from safe_spending.generator.events.stages import EXTRA_PAY_NOTE
from safe_spending.generator.money import CENTS_PER_EUR
from safe_spending.generator.savings.savings_plan import SavingsPlan

INTERNAL_CATEGORY = "Traspasos entre cuentas propias"
RETURN_DAYS = (10, 24)  # day of the month a return can happen on


class _Step(NamedTuple):
    day: date
    is_deposit: bool  # on the same day, a deposit goes before a return
    chance: float  # for a return: the draw that decides if it happens
    share: float  # for a return: the share of the balance that comes back


def savings_events(
        config: GeneratorConfig,
        catalog: Catalog,
        plan: SavingsPlan,
        events: list[Event],
        rng: np.random.Generator,
        end: date
) -> list[Event]:
    """The two movements of every transfer, in chronological order of the transfers.

    Deposits follow the pays in `events`, so they exist only for the history the user really has;
    a return needs a balance, so it cannot come before the first deposit.
    """
    settings = config.savings
    category_id = catalog.category(INTERNAL_CATEGORY).category_id
    step = settings.rounding_eur * CENTS_PER_EUR
    minimum_return = settings.min_return_eur * CENTS_PER_EUR
    balance = 0
    result = []

    schedule = sorted([*_deposits(events, plan, end), *_returns(config, rng, end)], key=lambda s: (s.day, not s.is_deposit))

    for transfer in schedule:
        if transfer.is_deposit:
            balance += plan.monthly_cents
            result += _pair(transfer.day, plan.monthly_cents, category_id, to_savings=True)
        elif transfer.chance < settings.return_probability and balance >= minimum_return:
            amount = max(step, int(balance * transfer.share // step) * step)
            balance -= amount
            result += _pair(transfer.day, amount, category_id, to_savings=False)

    return result


def _deposits(
        events: list[Event],
        plan: SavingsPlan,
        end: date
) -> list[_Step]:
    """One deposit a few days after each monthly pay (the extra pays of June and December excluded)."""
    days = [
        next_business_day(e.booking_date + timedelta(days=plan.delay_days))
        for e in events
        if e.tx_code == TxCode.SALARY and e.note != EXTRA_PAY_NOTE
    ]

    return [_Step(day, True, 0.0, 0.0) for day in days if day <= end]


def _returns(
        config: GeneratorConfig,
        rng: np.random.Generator,
        end: date
) -> list[_Step]:
    """A possible return in every month. The three draws are made for every month, used or not."""
    settings = config.savings
    candidates = []

    for year, month in months(config.period_start, end):
        chance = float(rng.random())
        share = float(rng.uniform(*settings.return_share))
        day = next_business_day(day_in_month(
            year=year,
            month=month,
            day=int(rng.integers(RETURN_DAYS[0], RETURN_DAYS[1] + 1))
        ))
        if config.period_start <= day <= end:
            candidates.append(_Step(day, False, chance, share))

    return candidates


def _pair(
        day: date,
        cents: int,
        category_id: int,
        to_savings: bool
) -> list[Event]:
    """The outgoing and the incoming movement of one transfer."""
    source, target = (AccountKind.CURRENT, AccountKind.SAVINGS) if to_savings else (AccountKind.SAVINGS, AccountKind.CURRENT)
    outgoing = Event(
        booking_date=day,
        value_date=day,
        tx_code=TxCode.TRANSFER_OUT,
        amount_cents=-cents,
        category_id=category_id,
        account=source,
        internal=True,
    )

    return [
        outgoing,
        outgoing.model_copy(update={"tx_code": TxCode.TRANSFER_IN, "amount_cents": cents, "account": target}),
    ]
