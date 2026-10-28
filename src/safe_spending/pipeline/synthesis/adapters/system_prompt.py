"""The synthesizer's system prompt: a versioned Spanish template.

Same rule as the generator's (`generation/adapters/system_prompt.py`): a version is a file,
`prompts/system_vN.md`, never edited once a run has used it, because every trace and eval log records it.
"""

from datetime import date
from functools import cache
from pathlib import Path
from string import Template

PROMPT_VERSION = "v2"
PROMPTS = Path(__file__).parent / "prompts"


@cache
def _template(version: str) -> Template:
    path = PROMPTS / f"system_{version}.md"
    if not path.is_file():
        raise ValueError(f"unknown prompt version {version!r}")

    return Template(path.read_text(encoding="utf-8"))


def render_system_prompt(
        today: date,
        version: str = PROMPT_VERSION
) -> str:
    return _template(version=version).substitute(today=today.isoformat())
