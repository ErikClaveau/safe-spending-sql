"""The docs exist in English (docs/) and Spanish (docs/es/), each linking to the other.

English is the main language; the Spanish mirror lives at the same relative path under `docs/es/`. A few
documents are deliberately in one language only; they are listed here with the reason, so adding one is a
visible decision.
"""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).parents[2] / "docs"
SPANISH = DOCS / "es"

SPANISH_ONLY = {
    "proyecto-1-asistente-gastos-final.md": "the working plan, internal",
    "iteraciones-evals.md": "a table of eval runs and their notes",
}
ENGLISH_ONLY = {
    "data-dictionary.md": "the English layer of the semantic views (ADR-005), checked against the database",
}

LINK = re.compile(r"^> 🇬🇧 English: \[[^\]]+\]\(([^)]+)\)|^> 🇪🇸 Español: \[[^\]]+\]\(([^)]+)\)", re.MULTILINE)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _english_documents() -> list[Path]:
    return sorted(
        p for p in DOCS.rglob("*.md")
        if SPANISH not in p.parents and _relative(p, DOCS) not in SPANISH_ONLY | ENGLISH_ONLY
    )


def _spanish_documents() -> list[Path]:
    return sorted(SPANISH.rglob("*.md"))


def _link_of(path: Path) -> str | None:
    match = LINK.search(path.read_text(encoding="utf-8"))
    return (match.group(1) or match.group(2)) if match else None


@pytest.mark.parametrize("english", _english_documents(), ids=lambda p: _relative(p, DOCS))
def test_every_english_document_has_a_spanish_mirror_that_it_links_to(english):
    mirror = SPANISH / english.relative_to(DOCS)

    assert mirror.exists(), f"{_relative(english, DOCS)} has no Spanish mirror at docs/es/"
    link = _link_of(english)
    assert link is not None, f"{_relative(english, DOCS)} does not link to its Spanish version"
    assert (english.parent / link).resolve() == mirror.resolve()


@pytest.mark.parametrize("spanish", _spanish_documents(), ids=lambda p: _relative(p, SPANISH))
def test_every_spanish_document_has_an_english_original_that_it_links_to(spanish):
    original = DOCS / spanish.relative_to(SPANISH)

    assert original.exists(), f"docs/es/{_relative(spanish, SPANISH)} has no English original"
    link = _link_of(spanish)
    assert link is not None, f"docs/es/{_relative(spanish, SPANISH)} does not link to its English version"
    assert (spanish.parent / link).resolve() == original.resolve()


def test_the_one_language_exceptions_exist_and_have_no_mirror():
    for name in SPANISH_ONLY | ENGLISH_ONLY:
        assert (DOCS / name).exists(), f"{name} is listed as an exception but does not exist"
        assert not (SPANISH / name).exists(), f"{name} is an exception but has a mirror"
