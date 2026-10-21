class IdentityNotSetError(Exception):
    """The user identity could not be confirmed in the transaction, so the query was not run."""
