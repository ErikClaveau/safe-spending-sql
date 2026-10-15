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
