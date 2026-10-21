import hashlib

from pydantic import BaseModel, ConfigDict, Field, computed_field

from safe_spending.pipeline.schema.category_doc import CategoryDoc
from safe_spending.pipeline.schema.view_doc import ViewDoc


class SemanticSchema(BaseModel):
    """Everything the LLM may know about the data: the semantic views and the closed category list."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    views: tuple[ViewDoc, ...]
    categories: tuple[CategoryDoc, ...] = Field(description="The closed list the `categoria` columns draw from.")

    @computed_field
    @property
    def version(self) -> str:
        """Content hash: any change to a name, type, comment or category gives another version.

        Every trace and every eval log records it (plan sections 9.3 and 10), so two runs are
        only comparable when it is the same.
        """
        content = self.model_dump_json(exclude={"version"})

        return hashlib.sha256(content.encode()).hexdigest()[:12]
