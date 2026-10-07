"""Exceptions of the database layer."""


class ManifestError(Exception):
    """The dataset manifest is missing, malformed, or does not match the files on disk."""
