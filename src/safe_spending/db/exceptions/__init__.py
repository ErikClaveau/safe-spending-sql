"""Exceptions of the database layer."""

from safe_spending.db.exceptions.identity_not_set_error import IdentityNotSetError
from safe_spending.db.exceptions.manifest_error import ManifestError

__all__ = ["IdentityNotSetError", "ManifestError"]
