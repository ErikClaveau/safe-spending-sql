"""Parquet export and manifest (design 3.3).

    <out>/operational/{categories,merchants,users,accounts,transactions}.parquet
    <out>/labels/{tx_labels,user_labels,scenarios}.parquet     (never loaded into Postgres)
    <out>/manifest.json

The manifest carries no timestamp: the same config and seed must give byte-identical files
and manifest, which a CI test checks by comparing hashes.
"""

import hashlib
import json
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from safe_spending.generator.config import GeneratorConfig
from safe_spending.generator.simulate import Dataset
from safe_spending.schemas import FileInfo, Manifest, Period
from safe_spending.tables import LABELS, OPERATIONAL


MONEY = pa.decimal128(12, 2)

SCHEMAS = {
    "categories": pa.schema([("category_id", pa.int32()), ("name", pa.string()), ("group_name", pa.string())]),
    "merchants": pa.schema([("merchant_id", pa.int32()), ("normalized_name", pa.string()), ("mcc", pa.string())]),
    "users": pa.schema([("user_id", pa.int32()), ("name", pa.string()), ("city", pa.string()), ("signup_date", pa.date32())]),
    "accounts": pa.schema([("account_id", pa.int32()), ("user_id", pa.int32()), ("iban", pa.string()), ("currency", pa.string())]),
    "transactions": pa.schema([
        ("tx_id", pa.int64()), ("account_id", pa.int32()), ("user_id", pa.int32()),
        ("booking_date", pa.date32()), ("value_date", pa.date32()),
        ("amount", MONEY), ("currency", pa.string()), ("exchange_rate", pa.decimal128(12, 6)), ("amount_eur", MONEY),
        ("description_raw", pa.string()), ("counterparty", pa.string()), ("tx_code", pa.string()),
        ("merchant_id", pa.int32()), ("category_id", pa.int32()), ("counterparty_account_id", pa.int32()),
    ]),
    "tx_labels": pa.schema([
        ("tx_id", pa.int64()), ("true_category_id", pa.int32()), ("scenario_id", pa.string()),
        ("is_trap", pa.bool_()), ("trap_type", pa.string()), ("canary", pa.string()), ("refund_of_tx_id", pa.int64()),
    ]),
    "user_labels": pa.schema([
        ("user_id", pa.int32()), ("archetype", pa.string()), ("monthly_income", MONEY), ("split", pa.string()),
    ]),
    "scenarios": pa.schema([
        ("scenario_id", pa.string()), ("user_id", pa.int32()), ("type", pa.string()),
        ("params", pa.string()), ("description", pa.string()),
    ]),
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_dataset(
        dataset: Dataset,
        out_dir: Path,
        config: GeneratorConfig,
        end: date,
        config_hash: str
) -> Manifest:
    out_dir = Path(out_dir)
    files = {}
    for group, tables in (("operational", OPERATIONAL), ("labels", LABELS)):
        (out_dir / group).mkdir(
            parents=True,
            exist_ok=True
        )
        for table in tables:
            path = out_dir / group / f"{table}.parquet"
            arrow = pa.Table.from_pylist(
                [row.model_dump() for row in getattr(dataset, table)],
                schema=SCHEMAS[table]
            )
            pq.write_table(
                table=arrow,
                where=path,
                compression="zstd"
            )
            files[f"{group}/{table}.parquet"] = FileInfo(
                rows=arrow.num_rows,
                sha256=sha256_of(path)
            )

    manifest = Manifest(
        dataset_version=config.dataset_version,
        seed=config.seed,
        config_hash=config_hash,
        reference_date=end,
        period=Period(start=config.period_start, end=end),
        files=files
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(
            manifest.model_dump(mode="json"),
            indent=2,
            sort_keys=True
        ) + "\n", encoding="utf-8"
    )

    return manifest
