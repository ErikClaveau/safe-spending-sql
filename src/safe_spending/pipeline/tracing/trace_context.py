import os
import subprocess

from safe_spending.pipeline.assistant import TraceContext

COMMIT_SHA_VARIABLE = "COMMIT_SHA"
USER_SALT_VARIABLE = "TRACE_USER_SALT"
UNKNOWN_COMMIT = "unknown"


def current_commit_sha() -> str:
    """The commit the process runs: `COMMIT_SHA` if set (images, CI), else git's short hash.

    A working tree with uncommitted changes gets `-dirty`, so a trace never claims a commit it does not match.
    `unknown` if there is neither the variable nor a git repository.
    """
    from_environment = os.environ.get(COMMIT_SHA_VARIABLE)
    if from_environment:
        return from_environment

    try:
        sha = _git("rev-parse", "--short", "HEAD")
        dirty = bool(_git("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        return UNKNOWN_COMMIT

    return f"{sha}-dirty" if dirty else sha


def trace_context_from_environment(default_salt: str | None = None) -> TraceContext:
    """The context a process needs to trace: the commit and the secret of the user pseudonym.

    The salt comes from `TRACE_USER_SALT`. Without it, `default_salt` is used if the caller gives one
    (the evals do: their users are synthetic); a service that has none must not start.
    """
    salt = os.environ.get(USER_SALT_VARIABLE) or default_salt
    if not salt:
        raise RuntimeError(f"{USER_SALT_VARIABLE} is not set: traces would not have a safe user pseudonym")

    return TraceContext(
        commit_sha=current_commit_sha(),
        user_salt=salt
    )


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()
