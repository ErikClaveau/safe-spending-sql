from pydantic import Field

from safe_spending.schemas._base import _Frozen


class FileInfo(_Frozen):
    rows: int = Field(description="Number of rows in the file.")
    sha256: str = Field(description="SHA-256 hex digest of the file content.")
