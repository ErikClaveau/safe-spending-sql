"""The generator's system prompt: a versioned Spanish template filled with the live schema.

A prompt version is a file, `prompts/system_vN.md`, and is never edited once a run has used it: a change
that can alter results is a new file and a new `PROMPT_VERSION`, because every trace and eval log records
it (plan sections 9.3 and 10). Older versions stay loadable so a run can be repeated or compared.
"""

from datetime import date
from functools import cache
from itertools import groupby
from pathlib import Path
from string import Template

from safe_spending.pipeline.schema import SemanticSchema, ViewDoc

PROMPT_VERSION = "v4"
PROMPTS = Path(__file__).parent / "prompts"


@cache
def _template(version: str) -> Template:
    path = PROMPTS / f"system_{version}.md"
    if not path.is_file():
        raise ValueError(f"unknown prompt version {version!r}")

    return Template(path.read_text(encoding="utf-8"))


def render_system_prompt(
        schema: SemanticSchema,
        today: date,
        version: str = PROMPT_VERSION
) -> str:
    return _template(version=version).substitute(
        today=today.isoformat(),
        schema="\n\n".join(_render_view(view) for view in schema.views),
        categories=_render_categories(schema),
    )


def _render_view(view: ViewDoc) -> str:
    columns = "\n".join(f"- `{column.name}` ({column.data_type}): {column.description}" for column in view.columns)

    return f"### {view.name}\n{view.description}\n\n{columns}"


def _render_categories(schema: SemanticSchema) -> str:
    # The schema orders categories by group, then by name
    return "\n".join(
        f"- {group}: " + ", ".join(category.name for category in categories)
        for group, categories in groupby(schema.categories, key=lambda category: category.group_name)
    )
