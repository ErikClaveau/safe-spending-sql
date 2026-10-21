"""The `SchemaProvider` port: where the prompt gets what it may say about the data."""

from typing import Protocol

from safe_spending.pipeline.schema.semantic_schema import SemanticSchema


class SchemaProvider(Protocol):
    def get_schema(self) -> SemanticSchema: ...
