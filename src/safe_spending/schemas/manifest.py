from datetime import date

from pydantic import Field

from safe_spending.schemas._base import _Frozen
from safe_spending.schemas.file_info import FileInfo
from safe_spending.schemas.period import Period


class Manifest(_Frozen):
    dataset_version: str = Field(description="Version of the generated data; bumped whenever it changes.")
    seed: int = Field(description="Root seed of all random streams.")
    config_hash: str = Field(description="Hash of the generator configuration used.")
    reference_date: date = Field(description="Frozen 'today' of the dataset, from the Clock port.")
    period: Period = Field(description="Dates covered by the dataset.")
    files: dict[str, FileInfo] = Field(
        description='Rows and checksum of each file, keyed by "<group>/<table>.parquet".'
    )

    def differences(self, other: "Manifest") -> list[str]:
        """What differs from `other`, one line each; empty when both describe the same dataset."""
        found = []
        for name in ("dataset_version", "seed", "config_hash", "reference_date", "period"):
            if getattr(self, name) != getattr(other, name):
                found.append(f"{name}: {getattr(self, name)} -> {getattr(other, name)}")
        for key in sorted(self.files.keys() | other.files.keys()):
            mine, theirs = self.files.get(key), other.files.get(key)
            if mine is None:
                found.append(f"{key}: not in the reference manifest")
            elif theirs is None:
                found.append(f"{key}: missing")
            elif mine.rows != theirs.rows:
                found.append(f"{key}: {mine.rows} rows -> {theirs.rows} rows")
            elif mine.sha256 != theirs.sha256:
                found.append(f"{key}: same rows, different content")
        return found
