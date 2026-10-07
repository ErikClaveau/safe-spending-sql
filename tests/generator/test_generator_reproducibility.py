"""Reproducibility guarantees (generator design 6.1): same input, same bytes; independent users."""

import json
from datetime import date

import pytest

from gen_helpers import REFERENCE, build, write
from safe_spending.generator.config import configuration_hash
from safe_spending.schemas import Manifest, Period


def test_same_config_and_seed_give_byte_identical_files(tmp_path):
    first = write(tmp_path / "a")
    second = write(tmp_path / "b")
    assert first == second
    assert (tmp_path / "a" / "manifest.json").read_bytes() == (tmp_path / "b" / "manifest.json").read_bytes()
    for name in first.files:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_a_different_seed_gives_different_data():
    _, _, one = build(3, seed=1)
    _, _, two = build(3, seed=2)
    assert one.transactions != two.transactions


@pytest.mark.parametrize("extra_users", [1, 3])
def test_adding_users_does_not_change_existing_ones(extra_users):
    _, _, small = build(4)
    _, _, large = build(4 + extra_users)
    for table in ("users", "accounts", "user_labels"):
        assert getattr(large, table)[:4] == getattr(small, table)
    kept = [t for t in large.transactions if t.user_id <= 4]
    assert kept == small.transactions
    assert [l for l in large.tx_labels if l.tx_id // 1_000_000 <= 4] == small.tx_labels


def test_user_data_does_not_depend_on_the_population_size():
    # The strongest form: user 2 alone equals user 2 inside a larger run.
    _, _, large = build(6)
    _, _, small = build(2)
    assert [t for t in large.transactions if t.user_id == 2] == [t for t in small.transactions if t.user_id == 2]


def test_manifest_content_and_hashes(tmp_path):
    import hashlib

    manifest = write(tmp_path)
    on_disk = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert Manifest.model_validate(on_disk) == manifest
    assert manifest.config_hash == configuration_hash()
    assert manifest.reference_date == date(2026, 9, 15)
    assert manifest.period == Period(start=date(2024, 9, 16), end=date(2026, 9, 15))
    assert manifest.seed == 20260915
    for name, info in manifest.files.items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == info.sha256
    # No timestamp or machine-specific field: it would break byte-for-byte reproducibility.
    assert set(on_disk) == {"dataset_version", "seed", "config_hash", "reference_date", "period", "files"}


def test_labels_live_apart_from_the_operational_tables(tmp_path):
    manifest = write(tmp_path)
    operational = {n for n in manifest.files if n.startswith("operational/")}
    labels = {n for n in manifest.files if n.startswith("labels/")}
    assert {n.split("/")[1] for n in operational} == {
        "categories.parquet", "merchants.parquet", "users.parquet", "accounts.parquet", "transactions.parquet",
    }
    assert {n.split("/")[1] for n in labels} == {"tx_labels.parquet", "user_labels.parquet", "scenarios.parquet"}


def test_the_clock_port_decides_today_not_the_system_date():
    _, _, dataset = build(3, today=date(2025, 12, 31))
    assert max(t.booking_date for t in dataset.transactions) <= date(2025, 12, 31)
    assert max(t.booking_date for t in dataset.transactions) > date(2025, 12, 1)
    assert REFERENCE > date(2025, 12, 31)
