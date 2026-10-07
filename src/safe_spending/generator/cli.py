"""    uv run safe-spending-generate [--config PATH] [--out DIR] [--users N]"""

import argparse
from pathlib import Path

from safe_spending.clock import FixedClock
from safe_spending.generator.config import CONFIG_FILE, configuration_hash, load_catalog, load_config
from safe_spending.generator.export import write_dataset
from safe_spending.generator.simulate import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic banking dataset (Parquet + manifest).")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--out", type=Path, default=Path("data/dataset"))
    parser.add_argument("--users", type=int, help="override n_users from the config")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.users:
        config = config.model_copy(update={"n_users": args.users})
    clock = FixedClock(config.reference_date)
    dataset = generate(config, load_catalog(), clock)
    manifest = write_dataset(dataset, args.out, config, clock.today(), configuration_hash(args.config))

    rows = {name: info.rows for name, info in manifest.files.items()}
    print(f"ok  dataset {config.dataset_version} written to {args.out}")
    for name, count in rows.items():
        print(f"    {name}: {count} rows")


if __name__ == "__main__":
    main()
