from safe_spending.schemas._base import _Frozen


class FileInfo(_Frozen):
    rows: int
    sha256: str
