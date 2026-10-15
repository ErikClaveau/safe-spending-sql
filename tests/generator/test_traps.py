"""Injection traps (generator design 5.6): incoming Bizum and transfers whose concept carries a
prompt injection and a unique canary word, planted only in the adversarial users."""

import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest
from pydantic import ValidationError

from gen_helpers import REFERENCE, build
from safe_spending.clock import FixedClock
from safe_spending.generator import text
from safe_spending.generator.config import (
    CANARY_PLACEHOLDER,
    TRAP_CHANNELS,
    TrapTemplates,
)
from safe_spending.generator.enums import TrapType, TxCode
from safe_spending.generator.simulate import generate
from safe_spending.generator.traps import trap_events
from safe_spending.generator.traps.canary import ALPHABET, new_canary

ADVERSARIAL_USERS = {16, 17, 18, 19, 20}
N_USERS = 20
CANARY = re.compile(rf"^CNR(\d{{3}})[{ALPHABET}]{{4}}$")
WORST_CASE_CANARY = "CNR999" + ALPHABET[-1] * 4  # as long as a real canary


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
def traps(dataset):
    """(transaction, label) for every trap, in transaction order."""
    labels = {l.tx_id: l for l in dataset.tx_labels}
    return [(t, labels[t.tx_id]) for t in dataset.transactions if labels[t.tx_id].is_trap]


def by_user(traps):
    grouped = defaultdict(list)
    for transaction, label in traps:
        grouped[transaction.user_id].append((transaction, label))
    return grouped


def concept_of(transaction):
    return transaction.description_raw.split(" CONCEPTO ", 1)[1]


# ---------------------------------------------------------------------------
# Who gets traps and how many
# ---------------------------------------------------------------------------


def test_only_the_adversarial_users_have_traps(traps):
    assert set(by_user(traps)) == ADVERSARIAL_USERS


def test_every_adversarial_user_gets_every_trap_type(traps):
    for user_id, rows in by_user(traps).items():
        assert {label.trap_type for _, label in rows} == set(TrapType), user_id


def test_each_user_gets_one_of_each_type_plus_a_few_repetitions(traps, config):
    low, high = config.traps.extra_per_user
    for user_id, rows in by_user(traps).items():
        assert len(TrapType) + low <= len(rows) <= len(TrapType) + high, user_id


def test_a_population_without_adversarial_users_has_no_traps(config, catalog):
    for user_id in (1, 8, 15, 21, 100):
        assert trap_events(config, catalog, user_id, REFERENCE) == []


# ---------------------------------------------------------------------------
# Canaries: unique, well formed and intact in the statement
# ---------------------------------------------------------------------------


def test_canaries_are_unique_across_the_dataset(traps):
    canaries = [label.canary for _, label in traps]
    assert len(canaries) == len(set(canaries)) > 20


def test_a_canary_has_the_expected_shape_and_carries_its_user_id(traps):
    for transaction, label in traps:
        match = CANARY.match(label.canary)
        assert match, label.canary
        assert int(match.group(1)) == transaction.user_id


def test_the_canary_is_in_the_statement_exactly_once(traps):
    for transaction, label in traps:
        assert transaction.description_raw.count(label.canary) == 1


def test_a_canary_appears_nowhere_else_in_the_dataset(dataset, traps):
    canaries = {label.canary: transaction.tx_id for transaction, label in traps}
    for transaction in dataset.transactions:
        for canary, owner_tx in canaries.items():
            if transaction.tx_id != owner_tx:
                assert canary not in transaction.description_raw
                assert canary not in (transaction.counterparty or "")


def test_a_canary_is_drawn_again_if_it_was_already_used():
    rng = np.random.default_rng(0)
    used: set[str] = set()
    canaries = [new_canary(rng, 16, "CNR", 1, used) for _ in range(len(ALPHABET))]
    assert len(set(canaries)) == len(ALPHABET)  # a 1-character suffix leaves exactly 32 options
    assert used == set(canaries)


# ---------------------------------------------------------------------------
# A trap is a real movement
# ---------------------------------------------------------------------------


def test_traps_are_incoming_bizum_and_transfers(traps):
    assert {t.tx_code for t, _ in traps} == {TxCode.BIZUM_IN, TxCode.TRANSFER_IN}
    for transaction, _ in traps:
        assert transaction.amount_eur == transaction.amount > 0
        assert transaction.currency == "EUR" and transaction.exchange_rate is None
        assert transaction.merchant_id is None and transaction.counterparty_account_id is None


def test_trap_amounts_are_small_and_bizum_is_in_whole_euros(traps, config):
    low, high = config.traps.amount_eur
    for transaction, _ in traps:
        assert Decimal(low) <= transaction.amount_eur <= Decimal(high)
        if transaction.tx_code == TxCode.BIZUM_IN:
            assert transaction.amount_eur == transaction.amount_eur.to_integral_value()


def test_traps_are_filed_as_received_money(traps, dataset):
    received = next(c.category_id for c in dataset.categories if c.name == "Bizum y transferencias recibidas")
    assert {t.category_id for t, _ in traps} == {received}
    assert {label.true_category_id for _, label in traps} == {received}


def test_the_sender_is_a_person_and_not_a_merchant(traps, dataset):
    merchants = {m.normalized_name for m in dataset.merchants}
    for transaction, _ in traps:
        assert transaction.counterparty and transaction.counterparty not in merchants
        # The statement shows the sender's name (upper case, ASCII) before the concept.
        sender = text.statement(transaction.counterparty, 10_000)
        assert sender in transaction.description_raw.split(" CONCEPTO ", 1)[0]


def test_dates_are_inside_the_period_and_transfers_on_business_days(traps, config):
    first = config.period_start + timedelta(days=30)
    for transaction, _ in traps:
        assert first <= transaction.booking_date <= REFERENCE
        assert transaction.value_date == transaction.booking_date
        if transaction.tx_code == TxCode.TRANSFER_IN:
            assert transaction.booking_date.weekday() < 5


def test_statements_read_like_incoming_bizum_and_transfers(traps):
    for transaction, _ in traps:
        prefix = "BIZUM DE " if transaction.tx_code == TxCode.BIZUM_IN else "TRANSFERENCIA RECIBIDA DE "
        assert transaction.description_raw.startswith(prefix)
        assert " CONCEPTO " in transaction.description_raw


def test_trap_labels_do_not_carry_a_scenario(traps):
    assert all(label.scenario_id is None for _, label in traps)


# ---------------------------------------------------------------------------
# The limits of a concept never cut a canary
# ---------------------------------------------------------------------------


def test_concepts_respect_the_bizum_and_transfer_limits(traps, config):
    for transaction, _ in traps:
        assert len(concept_of(transaction)) <= config.traps.concept_limit(transaction.tx_code)
        assert len(transaction.description_raw) <= config.statement_limit(transaction.tx_code)


def test_every_template_fits_its_channel_with_a_canary_of_real_length(catalog, config):
    # The structural guarantee: it holds for any draw, not only for the ones in this dataset.
    for trap_type, channels in catalog.trap_templates.templates.items():
        for tx_code, templates in channels.items():
            limit = config.traps.concept_limit(tx_code)
            for template in templates:
                concept = text.statement(template.replace(CANARY_PLACEHOLDER, WORST_CASE_CANARY), 10_000)
                assert len(concept) <= limit, (trap_type, tx_code, template)
                assert WORST_CASE_CANARY in concept


def test_the_longest_statement_still_holds_the_canary(catalog, config):
    long_sender = "Maria de los Angeles Fernandez de la Vega y Sanchez-Cortes del Rio"  # beyond any Faker name
    for trap_type, channels in catalog.trap_templates.templates.items():
        for tx_code, templates in channels.items():
            for template in templates:
                concept = template.replace(CANARY_PLACEHOLDER, WORST_CASE_CANARY)
                raw = text.bizum_in(long_sender, concept) if tx_code == TxCode.BIZUM_IN else text.transfer_in(long_sender, concept)
                assert WORST_CASE_CANARY in text.statement(raw, config.statement_limit(tx_code))


def test_a_concept_over_the_limit_fails_loudly(config, catalog):
    tight = config.model_copy(update={"traps": config.traps.model_copy(update={
        "bizum_concept_max_length": 10, "transfer_concept_max_length": 10})})
    with pytest.raises(ValueError, match="longer than 10 characters"):
        trap_events(tight, catalog, 16, REFERENCE)


def test_a_statement_limit_that_would_cut_the_canary_fails_loudly(config, catalog):
    tight = config.model_copy(update={"statement_max_length_by_code": {TxCode.BIZUM_IN: 30, TxCode.TRANSFER_IN: 30}})
    with pytest.raises(ValueError, match="would cut the canary"):
        trap_events(tight, catalog, 16, REFERENCE)


def test_statement_limits_default_to_the_general_one(config):
    assert config.statement_limit(TxCode.CARD_PURCHASE) == config.statement_max_length
    assert config.statement_limit(TxCode.BIZUM_IN) > config.statement_max_length
    assert config.statement_limit(TxCode.TRANSFER_IN) > config.statement_limit(TxCode.BIZUM_IN)


# ---------------------------------------------------------------------------
# The repertoire (traps.yaml)
# ---------------------------------------------------------------------------


def valid_templates(catalog):
    return {t: {c: list(texts) for c, texts in channels.items()} for t, channels in catalog.trap_templates.templates.items()}


def test_the_repertoire_covers_every_type_and_channel_with_variety(catalog):
    for trap_type in TrapType:
        for channel in TRAP_CHANNELS:
            texts = catalog.trap_templates.for_(trap_type, channel)
            assert len(set(texts)) == len(texts) >= 2


def test_the_repertoire_mixes_spanish_and_english(catalog):
    texts = [t for channels in catalog.trap_templates.templates.values() for ts in channels.values() for t in ts]
    assert any("Ignore all previous" in t or "SYSTEM" in t for t in texts)
    assert any("responde" in t.lower() or "ignora" in t.lower() for t in texts)


def test_a_repertoire_missing_a_type_is_rejected(catalog):
    incomplete = valid_templates(catalog)
    del incomplete[TrapType.SQL_LOOKALIKE]
    with pytest.raises(ValidationError, match="sql_lookalike"):
        TrapTemplates(templates=incomplete)


def test_a_template_needs_the_canary_exactly_once(catalog):
    for bad in ("NO PLACEHOLDER HERE", f"{CANARY_PLACEHOLDER} AND {CANARY_PLACEHOLDER}"):
        broken = valid_templates(catalog)
        broken[TrapType.DIRECT_INSTRUCTION][TxCode.BIZUM_IN][0] = bad
        with pytest.raises(ValidationError, match="exactly once"):
            TrapTemplates(templates=broken)


def test_a_repertoire_with_a_single_template_per_channel_is_rejected(catalog):
    thin = valid_templates(catalog)
    thin[TrapType.RECATEGORIZATION][TxCode.TRANSFER_IN] = thin[TrapType.RECATEGORIZATION][TxCode.TRANSFER_IN][:1]
    with pytest.raises(ValidationError, match="at least"):
        TrapTemplates(templates=thin)


# ---------------------------------------------------------------------------
# Traps mix with normal activity and do not disturb anything else
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def without_traps(config, catalog):
    """The same population with nobody in the adversarial split."""
    splits = {"eval_functional": (1, 15), "eval_adversarial": (900, 901), "population": (16, 100)}
    return generate(config.model_copy(update={"splits": splits}), catalog, FixedClock(REFERENCE))


def test_the_baseline_without_traps_really_has_none(without_traps):
    assert not any(l.is_trap for l in without_traps.tx_labels)


def test_the_normal_movements_of_adversarial_users_are_untouched(dataset, without_traps, traps):
    trap_ids = {t.tx_id for t, _ in traps}
    for user_id in ADVERSARIAL_USERS:
        normal = [t for t in dataset.transactions if t.user_id == user_id and t.tx_id not in trap_ids]
        baseline = [t for t in without_traps.transactions if t.user_id == user_id]
        # Same movements, descriptions included: the traps add no random draw to the text stream.
        key = lambda t: (t.booking_date, t.tx_code, t.amount_eur, t.merchant_id, t.description_raw)
        assert Counter(map(key, normal)) == Counter(map(key, baseline))


def test_traps_are_a_small_share_of_each_users_movements(dataset, traps):
    for user_id, rows in by_user(traps).items():
        total = sum(1 for t in dataset.transactions if t.user_id == user_id)
        assert len(rows) / total < 0.02
        assert any(t.tx_code == TxCode.SALARY for t in dataset.transactions if t.user_id == user_id)


def test_traps_barely_move_the_savings_rate_of_a_user(dataset, without_traps):
    def savings_rate(ds, user_id):
        amounts = [t.amount_eur for t in ds.transactions if t.user_id == user_id and t.counterparty_account_id is None]
        return sum(amounts) / sum(a for a in amounts if a > 0)

    for user_id in ADVERSARIAL_USERS:
        gap = savings_rate(dataset, user_id) - savings_rate(without_traps, user_id)
        assert Decimal(0) <= gap < Decimal("0.01"), user_id  # traps are small incoming amounts


# ---------------------------------------------------------------------------
# Reproducibility and independence
# ---------------------------------------------------------------------------


def test_traps_do_not_depend_on_the_population_size(dataset):
    _, _, larger = build(N_USERS + 5)
    first = [(t, l) for t, l in zip(dataset.transactions, dataset.tx_labels) if l.is_trap]
    again = [(t, l) for t, l in zip(larger.transactions, larger.tx_labels) if l.is_trap and t.user_id <= N_USERS]
    assert first == again


def test_a_different_seed_gives_different_traps(traps):
    _, _, other = build(N_USERS, seed=7)
    canaries = {l.canary for l in other.tx_labels if l.is_trap}
    assert canaries and canaries.isdisjoint({l.canary for _, l in traps})


def test_the_same_seed_gives_the_same_canaries(traps):
    _, _, again = build(N_USERS)
    assert [l.canary for l in again.tx_labels if l.is_trap] == [l.canary for _, l in traps]
