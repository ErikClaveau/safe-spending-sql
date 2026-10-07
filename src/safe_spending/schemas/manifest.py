from datetime import date

from safe_spending.schemas._base import _Frozen
from safe_spending.schemas.file_info import FileInfo
from safe_spending.schemas.period import Period


class Manifest(_Frozen):
    dataset_version: str
    seed: int
    config_hash: str
    reference_date: date
    period: Period
    files: dict[str, FileInfo]  # key: "<group>/<table>.parquet"
