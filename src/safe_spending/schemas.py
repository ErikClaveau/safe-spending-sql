"""Contract of `manifest.json`, shared by the generator (which writes it) and the loader.

Neutral on purpose, like `tables`: the loader must not import the generator. The manifest
carries no timestamp, so the same config and seed give a byte-identical file.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FileInfo(_Frozen):
    rows: int
    sha256: str


class Period(_Frozen):
    start: date
    end: date


class Manifest(_Frozen):
    dataset_version: str
    seed: int
    config_hash: str
    reference_date: date
    period: Period
    files: dict[str, FileInfo]  # key: "<group>/<table>.parquet"
