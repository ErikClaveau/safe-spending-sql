"""Orchestration: config + seed + clock -> in-memory dataset. A pure function.

The generator never touches the database or the filesystem; export.py writes files and
a separate loader (safe_spending.db.loader) takes them to Postgres.
"""

from safe_spending.clock import Clock
from safe_spending.generator import text
from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.enums import TxCode
from safe_spending.generator.events import Event, purchase_events, recurring_events
from safe_spending.generator.money import to_decimal
from safe_spending.generator.profile import Profile, build_profile
from safe_spending.generator.rng import stream
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

TX_ID_STRIDE = 1_000_000  # tx_id = user_id * stride + sequence: ids are independent per user
ACCOUNTS_PER_USER_STRIDE = 10


def describe(
        event: Event,
        profile: Profile,
        config: GeneratorConfig,
        rng
) -> str:
    match event.tx_code:
        case TxCode.CARD_PURCHASE:
            raw = text.card_purchase(event.merchant, profile.card_prefix, profile.city, rng)
        case TxCode.DIRECT_DEBIT:
            raw = text.direct_debit(event.merchant, rng)
        case TxCode.SALARY:
            raw = text.salary(profile.employer, extra=event.note == "extra")
        case TxCode.TRANSFER_OUT:
            raw = text.rent_transfer(profile.landlord, event.booking_date.month, event.booking_date.year)
        case code:
            raise ValueError(f"no description template for {code}")
    return text.statement(raw, config.statement_max_length)


def simulate_user(
        config: GeneratorConfig,
        catalog: Catalog,
        user_id: int,
        end
) -> UserSimulation:
    """Everything one user owns, from that user's own random streams only."""
    profile = build_profile(config, catalog, user_id)
    events = recurring_events(config, catalog, profile, stream(config.seed, user_id, "recurring"), end)
    events += purchase_events(config, catalog, profile, stream(config.seed, user_id, "purchases"), end)
    # Stable sort: ties on the same day keep their generation order.
    events.sort(key=lambda e: e.booking_date)

    text_rng = stream(config.seed, user_id, "text")
    account_id = user_id * ACCOUNTS_PER_USER_STRIDE + 1
    transactions, labels = [], []
    for sequence, event in enumerate(events, start=1):
        tx_id = user_id * TX_ID_STRIDE + sequence
        amount = to_decimal(event.amount_cents)
        transactions.append(TransactionRow(
            tx_id=tx_id,
            account_id=account_id,
            user_id=user_id,
            booking_date=event.booking_date,
            value_date=event.value_date,
            amount=amount,
            currency="EUR",
            exchange_rate=None,
            amount_eur=amount,
            description_raw=describe(event, profile, config, text_rng),
            counterparty=event.counterparty,
            tx_code=event.tx_code,
            merchant_id=event.merchant.merchant_id if event.merchant else None,
            category_id=event.category_id,
            counterparty_account_id=None,
        ))
        labels.append(TxLabelRow(tx_id=tx_id, true_category_id=event.category_id))

    return UserSimulation(
        user=UserRow(user_id=user_id, name=profile.name, city=profile.city, signup_date=config.period_start),
        account=AccountRow(account_id=account_id, user_id=user_id, iban=profile.iban, currency="EUR"),
        transactions=transactions,
        tx_labels=labels,
        user_label=UserLabelRow(
            user_id=user_id,
            archetype=profile.archetype,
            monthly_income=to_decimal(profile.monthly_income_cents),
            split=config.split_of(user_id),
        ),
    )


def generate(config: GeneratorConfig, catalog: Catalog, clock: Clock) -> Dataset:
    end = clock.today()
    dataset = Dataset()
    dataset.categories = [
        CategoryRow(category_id=c.category_id, name=c.name, group_name=c.group_name) for c in catalog.categories
    ]
    dataset.merchants = [
        MerchantRow(merchant_id=m.merchant_id, normalized_name=m.name, mcc=m.mcc) for m in catalog.merchants
    ]
    for user_id in range(1, config.n_users + 1):
        user = simulate_user(config, catalog, user_id, end)
        dataset.users.append(user.user)
        dataset.accounts.append(user.account)
        dataset.transactions.extend(user.transactions)
        dataset.tx_labels.extend(user.tx_labels)
        dataset.user_labels.append(user.user_label)
    return dataset
