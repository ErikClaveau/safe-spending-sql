"""Load a generated dataset into Postgres as `app_loader` (ADR-002).

Only the five operational tables are loaded. The ground-truth labels in labels/ are never
read here, so they cannot end up in the application database. The manifest is verified
first: a file whose SHA-256 differs from the manifest (or a missing file) aborts the load.

    uv run safe-spending-load [--data DIR] [--reset]

The load runs in one transaction. Loading twice without --reset fails on the primary keys
and rolls back. --reset first empties the five tables as `app_owner`, because `app_loader`
only has INSERT.
"""

import argparse
import hashlib
from pathlib import Path

import pyarrow.parquet as pq
from psycopg import sql
from pydantic import ValidationError

from safe_spending.db import settings
from safe_spending.db.exceptions import ManifestError
from safe_spending.schemas import Manifest
from safe_spending.tables import OPERATIONAL


def verify_manifest(data_dir: Path) -> Manifest:
    manifest_path = data_dir / "manifest.json"

    if not manifest_path.exists():
        raise ManifestError(f"no manifest.json in {data_dir}")

    try:
        manifest = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise ManifestError(f"manifest.json is not valid: {error}") from error

    for table in OPERATIONAL:
        key = f"operational/{table}.parquet"
        path = data_dir / key

        if key not in manifest.files:
            raise ManifestError(f"{key} is not in the manifest")
        if not path.exists():
            raise ManifestError(f"{key} is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest.files[key].sha256:
            raise ManifestError(f"{key} does not match its manifest hash")

    return manifest


def reset(dbname: str | None = None) -> None:
    with settings.connect(
            role=settings.APP_OWNER,
            dbname=dbname,
            autocommit=True
    ) as conn:
        conn.execute(sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(sql.Identifier(t) for t in reversed(OPERATIONAL))))


def load(
        data_dir: Path,
        *,
        dbname: str | None = None,
        reset_first: bool = False
) -> dict[str, int]:
    data_dir = Path(data_dir)
    verify_manifest(data_dir)

    if reset_first:
        reset(dbname)

    loaded = {}
    with settings.connect(settings.APP_LOADER, dbname) as conn:
        for table in OPERATIONAL:
            arrow = pq.read_table(data_dir / "operational" / f"{table}.parquet")
            columns = sql.SQL(", ").join(sql.Identifier(c) for c in arrow.column_names)
            statement = sql.SQL("COPY {} ({}) FROM STDIN").format(sql.Identifier(table), columns)

            with conn.cursor() as cursor, cursor.copy(statement) as copy:
                for row in arrow.to_pylist():
                    copy.write_row(tuple(row.values()))

            loaded[table] = arrow.num_rows

    return loaded  # leaving the `with` block commits the transaction


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a generated dataset into Postgres as app_loader.")
    parser.add_argument("--data", type=Path, default=Path("data/dataset"))
    parser.add_argument("--reset", action="store_true", help="empty the operational tables first")
    args = parser.parse_args()
    loaded = load(args.data, reset_first=args.reset)
    print(f"ok  loaded into {settings.NAME}")
    for table, count in loaded.items():
        print(f"    {table}: {count} rows")


if __name__ == "__main__":
    main()
