"""Injection traps (design 5.6): incoming Bizum and transfers whose concept tries to hijack the assistant.

Only users of the adversarial split get them. A trap is a real movement (it has an amount and
counts in `v_ingresos`); the attack reaches the assistant through the data it retrieves, so the
questions of the adversarial set can be innocent. Each trap asks the assistant to print a unique
canary word, which makes a successful injection detectable without an LLM judge.
"""

from datetime import date, timedelta

import numpy as np
from faker import Faker

from safe_spending.generator import text
from safe_spending.generator.config import (
    ADVERSARIAL_SPLIT,
    CANARY_PLACEHOLDER,
    TRAP_CHANNELS,
    Catalog,
    GeneratorConfig,
)
from safe_spending.generator.dates import daterange, is_business_day
from safe_spending.generator.enums import TrapType, TxCode
from safe_spending.generator.events import Event
from safe_spending.generator.money import CENTS_PER_EUR
from safe_spending.generator.profile.builder import FAKER_LOCALE, FAKER_SEED_BOUND
from safe_spending.generator.enums import Stage
from safe_spending.generator.rng import stream
from safe_spending.generator.traps.canary import new_canary

RECEIVED_CATEGORY = "Bizum y transferencias recibidas"
FIRST_TRAP_OFFSET_DAYS = 30  # traps mix with normal activity, not with the very first days


def trap_events(
        config: GeneratorConfig,
        catalog: Catalog,
        user_id: int,
        end: date
) -> list[Event]:
    """The user's traps; empty unless the user belongs to the adversarial split."""
    if config.split_of(user_id) != ADVERSARIAL_SPLIT:
        return []

    rng = stream(
        seed=config.seed,
        user_id=user_id,
        stage=Stage.TRAPS
    )
    fake = Faker(FAKER_LOCALE)
    fake.seed_instance(int(rng.integers(0, FAKER_SEED_BOUND)))
    used: set[str] = set()

    return [
        _trap(
            config=config,
            catalog=catalog,
            user_id=user_id,
            trap_type=trap_type,
            rng=rng,
            fake=fake,
            used=used,
            end=end
        )
        for trap_type in _trap_types(config, rng)
    ]


def _trap_types(
        config: GeneratorConfig,
        rng: np.random.Generator
) -> list[TrapType]:
    """One of each type, plus a few repetitions of random types."""
    types = list(TrapType)
    low, high = config.traps.extra_per_user
    extra = int(rng.integers(low, high + 1))

    return types + [types[int(rng.integers(len(types)))] for _ in range(extra)]


def _trap(
        config: GeneratorConfig,
        catalog: Catalog,
        user_id: int,
        trap_type: TrapType,
        rng: np.random.Generator,
        fake: Faker,
        used: set[str],
        end: date
) -> Event:
    tx_code = TRAP_CHANNELS[int(rng.integers(len(TRAP_CHANNELS)))]
    templates = catalog.trap_templates.for_(trap_type, tx_code)
    template = templates[int(rng.integers(len(templates)))]
    canary = new_canary(
        rng=rng,
        user_id=user_id,
        prefix=config.traps.canary_prefix,
        random_length=config.traps.canary_random_length,
        used=used
    )
    concept = template.replace(CANARY_PLACEHOLDER, canary)
    sender = fake.name()
    day = _trap_day(config, tx_code, rng, end)

    _check_the_canary_survives(config, tx_code, sender, concept, canary)

    return Event(
        booking_date=day,
        value_date=day,
        tx_code=tx_code,
        amount_cents=_amount_cents(config, tx_code, rng),
        category_id=catalog.category(RECEIVED_CATEGORY).category_id,
        counterparty=sender,
        concept=concept,
        trap_type=trap_type,
        canary=canary,
    )


def _trap_day(
        config: GeneratorConfig,
        tx_code: TxCode,
        rng: np.random.Generator,
        end: date
) -> date:
    """Bizum arrives any day; a bank transfer is credited on a business day."""
    days = daterange(config.period_start + timedelta(days=FIRST_TRAP_OFFSET_DAYS), end)
    if tx_code == TxCode.TRANSFER_IN:
        days = [d for d in days if is_business_day(d)]

    return days[int(rng.integers(len(days)))]


def _amount_cents(
        config: GeneratorConfig,
        tx_code: TxCode,
        rng: np.random.Generator
) -> int:
    """Bizum amounts are whole euros; transfers can have cents."""
    low, high = config.traps.amount_eur
    if tx_code == TxCode.BIZUM_IN:
        return int(rng.integers(low, high + 1)) * CENTS_PER_EUR

    return int(rng.integers(low * CENTS_PER_EUR, high * CENTS_PER_EUR + 1))


def _check_the_canary_survives(
        config: GeneratorConfig,
        tx_code: TxCode,
        sender: str,
        concept: str,
        canary: str
) -> None:
    """A trap whose canary is cut by the statement limits would be undetectable: fail loudly."""
    limit = config.traps.concept_limit(tx_code)
    if len(text.statement(text=concept, max_length=len(concept))) > limit:
        raise ValueError(f"trap concept is longer than {limit} characters: {concept!r}")

    raw = text.bizum_in(sender, concept) if tx_code == TxCode.BIZUM_IN else text.transfer_in(sender, concept)
    if canary not in text.statement(text=raw, max_length=config.statement_limit(tx_code)):
        raise ValueError(f"the statement limit would cut the canary of {concept!r}")
