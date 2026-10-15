"""Orchestration: config + seed + clock -> in-memory dataset. A pure function.

The generator never touches the database or the filesystem; export.py writes files and
a separate loader (safe_spending.db.loader) takes them to Postgres.
"""

from datetime import date

import numpy as np

from safe_spending.clock import Clock
from safe_spending.generator import text
from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.enums import AccountKind, TxCode
from safe_spending.generator.events import Event, purchase_events, recurring_events, refund_events
from safe_spending.generator.fx import FxSeries, build_fx_series
from safe_spending.generator.money import BASE_CURRENCY, to_decimal
from safe_spending.generator.profile import Profile, build_profile
from safe_spending.generator.enums import Stage
from safe_spending.generator.rng import stream
from safe_spending.generator.savings import SavingsPlan, build_savings
from safe_spending.generator.scenarios import apply_scenarios
from safe_spending.generator.schemas import (
    AccountRow,
    CategoryRow,
    MerchantRow,
    TransactionRow,
    TxLabelRow,
    UserLabelRow,
    UserRow,
    UserSimulation,
)
from safe_spending.generator.simulate.dataset import Dataset
from safe_spending.generator.traps import trap_events

TX_ID_STRIDE = 1_000_000  # tx_id = user_id * stride + sequence: ids are independent per user
ACCOUNTS_PER_USER_STRIDE = 10


def describe(
        event: Event,
        profile: Profile,
        config: GeneratorConfig,
        rng: np.random.Generator
) -> str:
    match event.tx_code:
        case TxCode.CARD_PURCHASE:
            raw = _card_purchase_text(event, profile, rng)
        case TxCode.CARD_REFUND:
            raw = text.card_refund(
                merchant=event.merchant,
                card_prefix=profile.card_prefix,
                rng=rng
            )
        case TxCode.FEE:
            raw = text.exchange_fee(reference=event.note)
        case TxCode.DIRECT_DEBIT:
            raw = text.direct_debit(
                merchant=event.merchant,
                rng=rng
            )
        case TxCode.SALARY:
            raw = text.salary(
                employer=event.counterparty,
                extra=event.note == "extra"
            )
        case TxCode.TRANSFER_OUT | TxCode.TRANSFER_IN if event.internal:
            raw = text.internal_transfer(
                outgoing=event.tx_code == TxCode.TRANSFER_OUT,
                other_account="CORRIENTE" if event.account == AccountKind.SAVINGS else "AHORRO"
            )
        case TxCode.TRANSFER_OUT:
            raw = text.rent_transfer(
                landlord=profile.landlord,
                month=event.booking_date.month,
                year=event.booking_date.year
            )
        case TxCode.BIZUM_IN:
            raw = text.bizum_in(
                sender=event.counterparty,
                concept=event.concept
            )
        case TxCode.TRANSFER_IN:
            raw = text.transfer_in(
                sender=event.counterparty,
                concept=event.concept
            )
        case code:
            raise ValueError(f"no description template for {code}")

    return text.statement(
        text=raw,
        max_length=config.statement_limit(event.tx_code)
    )


def simulate_user(
        config: GeneratorConfig,
        catalog: Catalog,
        fx: FxSeries,
        user_id: int,
        end: date
) -> UserSimulation:
    """Everything one user owns, from that user's own random streams only."""
    profile = build_profile(
        config=config,
        catalog=catalog,
        user_id=user_id
    )
    events = recurring_events(
        config=config,
        catalog=catalog,
        profile=profile,
        rng=stream(
            seed=config.seed,
            user_id=user_id,
            stage=Stage.RECURRING
        ),
        end=end
    )
    events += purchase_events(
        config=config,
        catalog=catalog,
        profile=profile,
        rng=stream(
            seed=config.seed,
            user_id=user_id,
            stage=Stage.PURCHASES
        ),
        end=end)
    events = refund_events(
        config=config,
        catalog=catalog,
        events=events,
        rng=stream(
            seed=config.seed,
            user_id=user_id,
            stage=Stage.SPECIAL
        ),
        end=end
    )
    scenarios = apply_scenarios(
        config=config,
        catalog=catalog,
        fx=fx,
        profile=profile,
        events=events,
        end=end
    )
    # After the scenarios: the deposits follow the pays the user really has (a recent sign-up has
    # none before its date), so the savings balance can never be built on history that is gone.
    savings = build_savings(
        config=config,
        catalog=catalog,
        profile=profile,
        events=list(scenarios.events),
        end=end
    )
    traps = trap_events(
        config=config,
        catalog=catalog,
        user_id=user_id,
        end=end
    )
    # Stable sort: ties on the same day keep their generation order.
    events = sorted(
        [*scenarios.events, *savings.events, *traps],
        key=lambda e: e.booking_date
    )

    text_rng = stream(
        seed=config.seed,
        user_id=user_id,
        stage=Stage.TEXT
    )
    account_ids = {
        AccountKind.CURRENT: user_id * ACCOUNTS_PER_USER_STRIDE + 1,
        AccountKind.SAVINGS: user_id * ACCOUNTS_PER_USER_STRIDE + 2,
    }
    tx_ids = [user_id * TX_ID_STRIDE + sequence for sequence in range(1, len(events) + 1)]
    tx_id_by_key = {e.key: tx_id for e, tx_id in zip(events, tx_ids) if e.key is not None}
    transactions, labels = [], []
    for tx_id, event in zip(tx_ids, events):
        amount, currency, exchange_rate = _original_amount(event)
        transactions.append(TransactionRow(
            tx_id=tx_id,
            account_id=account_ids[event.account],
            user_id=user_id,
            booking_date=event.booking_date,
            value_date=event.value_date,
            amount=amount,
            currency=currency,
            exchange_rate=exchange_rate,
            amount_eur=to_decimal(cents=event.amount_cents),
            description_raw=describe(
                event=event,
                profile=profile,
                config=config,
                rng=text_rng
            ),
            counterparty=event.counterparty,
            tx_code=event.tx_code,
            merchant_id=event.merchant.merchant_id if event.merchant else None,
            category_id=event.category_id,
            counterparty_account_id=_other_own_account_id(event, account_ids),
        ))
        labels.append(TxLabelRow(
            tx_id=tx_id,
            true_category_id=event.category_id,
            scenario_id=event.scenario_id,
            is_trap=event.trap_type is not None,
            trap_type=event.trap_type,
            canary=event.canary,
            refund_of_tx_id=tx_id_by_key[event.refund_of_key] if event.refund_of_key else None
        ))

    return UserSimulation(
        user=UserRow(
            user_id=user_id,
            name=profile.name,
            city=profile.city,
            signup_date=scenarios.signup_date or config.period_start,
        ),
        accounts=_accounts(user_id, profile, savings.plan, account_ids),
        transactions=transactions,
        tx_labels=labels,
        user_label=UserLabelRow(
            user_id=user_id,
            archetype=profile.archetype,
            monthly_income=to_decimal(profile.monthly_income_cents),
            split=config.split_of(user_id),
        ),
        scenarios=list(scenarios.rows),
    )


def generate(
        config: GeneratorConfig,
        catalog: Catalog,
        clock: Clock
) -> Dataset:
    end = clock.today()
    fx = build_fx_series(
        config=config,
        end=end
    )
    dataset = Dataset()
    dataset.categories = [
        CategoryRow(
            category_id=c.category_id,
            name=c.name,
            group_name=c.group_name
        )
        for c
        in catalog.categories
    ]
    dataset.merchants = [
        MerchantRow(
            merchant_id=m.merchant_id,
            normalized_name=m.name,
            mcc=m.mcc
        )
        for m
        in catalog.merchants
    ]
    for user_id in range(1, config.n_users + 1):
        user = simulate_user(
            config=config,
            catalog=catalog,
            fx=fx,
            user_id=user_id,
            end=end
        )
        dataset.users.append(user.user)
        dataset.accounts.extend(user.accounts)
        dataset.transactions.extend(user.transactions)
        dataset.tx_labels.extend(user.tx_labels)
        dataset.user_labels.append(user.user_label)
        dataset.scenarios.extend(user.scenarios)

    return dataset


def _card_purchase_text(
        event: Event,
        profile: Profile,
        rng: np.random.Generator
) -> str:
    if event.foreign is None:
        return text.card_purchase(
            merchant=event.merchant,
            card_prefix=profile.card_prefix,
            city=profile.city,
            rng=rng
        )

    return text.foreign_card_purchase(
        merchant=event.merchant,
        card_prefix=profile.card_prefix,
        amount=f"{to_decimal(cents=-event.foreign.amount_cents):.2f}",
        currency=event.foreign.currency,
        rng=rng
    )


def _original_amount(event: Event):
    """(amount, currency, exchange_rate) of the original operation; the euro amount is separate."""
    if event.foreign is None:
        return to_decimal(cents=event.amount_cents), BASE_CURRENCY, None

    return to_decimal(cents=event.foreign.amount_cents), event.foreign.currency, event.foreign.rate

def _other_own_account_id(
        event: Event,
        account_ids: dict[AccountKind, int]
) -> int | None:
    """For a transfer between the user's own accounts: the account on the other side."""
    if not event.internal:
        return None

    other = AccountKind.SAVINGS if event.account == AccountKind.CURRENT else AccountKind.CURRENT

    return account_ids[other]


def _accounts(
        user_id: int,
        profile: Profile,
        plan: SavingsPlan | None,
        account_ids: dict[AccountKind, int]
) -> list[AccountRow]:
    accounts = [AccountRow(
        account_id=account_ids[AccountKind.CURRENT],
        user_id=user_id,
        iban=profile.iban,
        currency=BASE_CURRENCY
    )]
    if plan is not None:
        accounts.append(AccountRow(
            account_id=account_ids[AccountKind.SAVINGS],
            user_id=user_id,
            iban=plan.iban,
            currency=BASE_CURRENCY
        ))

    return accounts
