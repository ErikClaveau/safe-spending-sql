"""The reproducibility gate (generator design 6.1): the official dataset is regenerated and its files'
hashes compared with the manifest committed in dataset/manifest.json.

The data is not in the repository, only this fingerprint. If the generator, its configuration, a
catalog or a dependency changes what it produces, this fails: on purpose, so that a change in the
data is a decision and not an accident. After an intended change, bump `dataset_version` in
config.yaml and refresh the fingerprint:

    uv run safe-spending-generate --update-reference-manifest

Byte-identical Parquet depends on the pinned pyarrow (uv.lock); a different platform or version can
change the hashes without the data having changed, which is the case to investigate before refreshing.
"""

import pytest

from safe_spending.clock import FixedClock
from safe_spending.evals.golden import load_golden_set, read_expected
from safe_spending.generator.config import configuration_hash, load_catalog, load_config
from safe_spending.generator.export import REFERENCE_MANIFEST, write_dataset
from safe_spending.generator.simulate import generate
from safe_spending.schemas import FileInfo, Manifest
from safe_spending.tables import LABELS, OPERATIONAL

HOW_TO_REFRESH = (
    "The official dataset no longer matches dataset/manifest.json. If the change is intended, bump "
    "dataset_version in config.yaml and run `uv run safe-spending-generate --update-reference-manifest`."
)


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def official_dataset(config):
    return generate(config, load_catalog(), FixedClock(config.reference_date))


def write(dataset, config, out_dir):
    return write_dataset(dataset, out_dir, config, config.reference_date, configuration_hash())


@pytest.fixture(scope="module")
def fresh(official_dataset, config, tmp_path_factory):
    return write(official_dataset, config, tmp_path_factory.mktemp("official"))


@pytest.fixture(scope="module")
def committed():
    return Manifest.model_validate_json(REFERENCE_MANIFEST.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_the_official_dataset_is_the_one_in_the_committed_manifest(committed, fresh):
    differences = committed.differences(fresh)
    assert differences == [], HOW_TO_REFRESH + "\n  " + "\n  ".join(differences)


def test_the_committed_manifest_is_of_the_current_configuration(committed, config):
    assert committed.config_hash == configuration_hash()
    assert committed.dataset_version == config.dataset_version
    assert committed.seed == config.seed
    assert committed.reference_date == config.reference_date


def test_the_committed_manifest_covers_every_table_and_the_whole_population(committed, config):
    expected_files = {f"operational/{t}.parquet" for t in OPERATIONAL} | {f"labels/{t}.parquet" for t in LABELS}
    assert set(committed.files) == expected_files
    assert committed.files["operational/users.parquet"].rows == config.n_users
    assert committed.files["labels/scenarios.parquet"].rows == len(config.scenarios)


def test_the_golden_set_was_written_for_this_dataset(committed):
    golden, expected = load_golden_set(), read_expected()
    assert golden.dataset_version == committed.dataset_version
    assert expected.dataset_version == committed.dataset_version
    assert expected.config_hash == committed.config_hash


# ---------------------------------------------------------------------------
# The gate really notices: negative controls
# ---------------------------------------------------------------------------


def test_a_single_cent_in_one_movement_changes_the_fingerprint(committed, official_dataset, config, tmp_path):
    first = official_dataset.transactions[0]
    nudged = first.model_copy(update={"amount_eur": first.amount_eur + 1, "amount": first.amount + 1})
    tampered = official_dataset.model_copy(update={"transactions": [nudged, *official_dataset.transactions[1:]]})
    differences = committed.differences(write(tampered, config, tmp_path))
    assert differences == ["operational/transactions.parquet: same rows, different content"]


def test_a_different_seed_changes_the_fingerprint(committed, config, tmp_path):
    other = config.model_copy(update={"seed": config.seed + 1})
    dataset = generate(other, load_catalog(), FixedClock(other.reference_date))
    differences = committed.differences(write(dataset, other, tmp_path))
    assert any(d.startswith("seed:") for d in differences)
    assert any("different content" in d for d in differences)


def test_a_dropped_user_changes_the_fingerprint(committed, config, tmp_path):
    smaller = config.model_copy(update={"n_users": config.n_users - 1})
    dataset = generate(smaller, load_catalog(), FixedClock(smaller.reference_date))
    differences = committed.differences(write(dataset, smaller, tmp_path))
    assert "operational/users.parquet: 25 rows -> 24 rows" in differences


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"dataset_version": "9.9.9"}, "dataset_version: 0.5.0 -> 9.9.9"),
        ({"config_hash": "0" * 64}, "config_hash:"),
        ({"seed": 1}, "seed:"),
    ],
)
def test_every_field_of_the_manifest_is_compared(committed, change, expected):
    assert any(d.startswith(expected) for d in committed.differences(committed.model_copy(update=change)))


def test_the_comparison_reports_rows_content_missing_and_extra_files(committed):
    files = dict(committed.files)
    files["labels/scenarios.parquet"] = FileInfo(rows=99, sha256=files["labels/scenarios.parquet"].sha256)
    files["labels/tx_labels.parquet"] = FileInfo(rows=files["labels/tx_labels.parquet"].rows, sha256="0" * 64)
    del files["operational/accounts.parquet"]
    files["operational/extra.parquet"] = FileInfo(rows=1, sha256="1" * 64)
    other = committed.model_copy(update={"files": files})

    assert committed.differences(other) == [
        "labels/scenarios.parquet: 7 rows -> 99 rows",
        "labels/tx_labels.parquet: same rows, different content",
        "operational/accounts.parquet: missing",
        "operational/extra.parquet: not in the reference manifest",
    ]


def test_identical_manifests_have_no_differences(committed):
    assert committed.differences(committed) == []
    assert committed.differences(Manifest.model_validate_json(committed.model_dump_json())) == []
