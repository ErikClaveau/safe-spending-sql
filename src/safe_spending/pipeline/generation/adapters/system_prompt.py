"""The generator's system prompt: a versioned Spanish template filled with the live schema.

Edit `prompts/system_v1.md` for wording changes that keep the same shape. Any change to the
text that can alter results needs a new `PROMPT_VERSION` (and a new file if the old one must
stay reproducible), because every trace and eval log records it (plan sections 9.3 and 10).
"""

from datetime import date
from itertools import groupby
from pathlib import Path
from string import Template

from safe_spending.pipeline.schema import SemanticSchema, ViewDoc

PROMPT_VERSION = "v1"

_TEMPLATE = Template((Path(__file__).parent / "prompts" / f"system_{PROMPT_VERSION}.md").read_text(encoding="utf-8"))


def render_system_prompt(
        schema: SemanticSchema,
        today: date
) -> str:
    return _TEMPLATE.substitute(
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
