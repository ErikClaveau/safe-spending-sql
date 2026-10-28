"""The trace context a process builds: the commit it runs and the salt of the user pseudonym."""

import subprocess

import pytest

from safe_spending.pipeline.tracing import current_commit_sha, trace_context_from_environment
from safe_spending.pipeline.tracing import trace_context as module


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    monkeypatch.delenv("COMMIT_SHA", raising=False)
    monkeypatch.delenv("TRACE_USER_SALT", raising=False)


def fake_git(monkeypatch, sha="abc1234", status=""):
    def run(*args):
        if args[0] == "rev-parse":
            return sha
        return status

    monkeypatch.setattr(module, "_git", run)


def test_the_environment_variable_wins_over_git(monkeypatch):
    monkeypatch.setenv("COMMIT_SHA", "from-the-image")
    fake_git(monkeypatch)

    assert current_commit_sha() == "from-the-image"


def test_git_gives_the_short_hash(monkeypatch):
    fake_git(monkeypatch)

    assert current_commit_sha() == "abc1234"


def test_uncommitted_changes_mark_the_commit_as_dirty(monkeypatch):
    fake_git(monkeypatch, status=" M src/file.py")

    assert current_commit_sha() == "abc1234-dirty"


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.CalledProcessError(128, "git")])
def test_without_git_the_commit_is_unknown(monkeypatch, error):
    def run(*args):
        raise error

    monkeypatch.setattr(module, "_git", run)

    assert current_commit_sha() == "unknown"


def test_the_salt_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("TRACE_USER_SALT", "secret")
    fake_git(monkeypatch)

    context = trace_context_from_environment(default_salt="default")

    assert context.user_salt == "secret"
    assert context.commit_sha == "abc1234"


def test_the_default_salt_is_used_only_if_the_caller_gives_one(monkeypatch):
    fake_git(monkeypatch)

    assert trace_context_from_environment(default_salt="default").user_salt == "default"
    with pytest.raises(RuntimeError, match="TRACE_USER_SALT"):
        trace_context_from_environment()
