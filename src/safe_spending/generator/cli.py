"""    uv run safe-spending-generate [--config PATH] [--out DIR] [--users N] [--update-reference-manifest]

`--update-reference-manifest` also copies the manifest to dataset/manifest.json, the committed
fingerprint of the official dataset that tests/generator/test_reference_manifest.py compares with.
Use it only after an intended change of the data, together with a new `dataset_version`.
"""

import argparse
import shutil
from pathlib import Path

from safe_spending.clock import FixedClock
from safe_spending.generator.config import CONFIG_FILE, configuration_hash, load_catalog, load_config
from safe_spending.generator.export import REFERENCE_MANIFEST, write_dataset
from safe_spending.generator.simulate import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic banking dataset (Parquet + manifest).")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--out", type=Path, default=Path("data/dataset"))
    parser.add_argument("--users", type=int, help="override n_users from the config")
    parser.add_argument(
        "--update-reference-manifest",
        action="store_true",
        help="also copy the manifest to dataset/manifest.json (official configuration only)",
    )
    args = parser.parse_args()

    if args.update_reference_manifest and (args.users or args.config != CONFIG_FILE):
        parser.error("--update-reference-manifest is only for the official configuration: no --users or --config")

    config = load_config(args.config)
    if args.users:
        config = config.model_copy(update={"n_users": args.users})
    clock = FixedClock(config.reference_date)
    dataset = generate(config, load_catalog(), clock)
    manifest = write_dataset(dataset, args.out, config, clock.today(), configuration_hash(args.config))

    if args.update_reference_manifest:
        REFERENCE_MANIFEST.parent.mkdir(exist_ok=True)
        shutil.copyfile(args.out / "manifest.json", REFERENCE_MANIFEST)
        print(f"ok  reference manifest updated: {REFERENCE_MANIFEST}")

    rows = {name: info.rows for name, info in manifest.files.items()}
    print(f"ok  dataset {config.dataset_version} written to {args.out}")
    for name, count in rows.items():
        print(f"    {name}: {count} rows")


if __name__ == "__main__":
    main()
