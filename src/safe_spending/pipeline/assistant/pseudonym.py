import hashlib
import hmac


def pseudonymize(
        user_id: int,
        salt: str
) -> str:
    """A stable reference to a user that does not reveal the id: the same user always gets the same one."""
    digest = hmac.new(
        key=salt.encode(),
        msg=str(user_id).encode(),
        digestmod=hashlib.sha256
    )

    return digest.hexdigest()[:16]
