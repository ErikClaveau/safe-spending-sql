"""Contract of `manifest.json`, shared by the generator (which writes it) and the loader.

Neutral on purpose, like `tables`: the loader must not import the generator. The manifest
carries no timestamp, so the same config and seed give a byte-identical file.
"""

from safe_spending.schemas.file_info import FileInfo
from safe_spending.schemas.manifest import Manifest
from safe_spending.schemas.period import Period

__all__ = ["FileInfo", "Manifest", "Period"]
