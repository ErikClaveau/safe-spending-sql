"""Reads the semantic layer from Postgres by introspection (ADR-005).

The documentation lives in `COMMENT ON` next to the views, so the prompt can never drift from
the database. It connects as `app_reader`, like the rest of the pipeline. The categories come
from the shared `categories` catalog (no personal data, no RLS); the LLM never queries it.
"""

from psycopg import Connection

from safe_spending.db import settings
from safe_spending.db.exceptions import SchemaDocumentationError
from safe_spending.pipeline.schema.category_doc import CategoryDoc
from safe_spending.pipeline.schema.column_doc import ColumnDoc
from safe_spending.pipeline.schema.schema_provider import SchemaProvider
from safe_spending.pipeline.schema.semantic_schema import SemanticSchema
from safe_spending.pipeline.schema.view_doc import ViewDoc

_VIEWS = """
    SELECT c.oid, c.relname, obj_description(c.oid, 'pg_class')
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'v'
    ORDER BY c.relname
"""

_COLUMNS = """
    SELECT a.attname, format_type(a.atttypid, a.atttypmod), col_description(a.attrelid, a.attnum)
    FROM pg_attribute a
    WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY a.attnum
"""

_CATEGORIES = f"SELECT name, group_name FROM {settings.SCHEMA}.categories ORDER BY group_name, name"


class PostgresSchemaProvider(SchemaProvider):
    def __init__(
            self,
            dbname: str | None = None
    ) -> None:
        self._dbname = dbname

    def get_schema(self) -> SemanticSchema:
        with settings.connect(
                role=settings.APP_READER,
                dbname=self._dbname
        ) as conn:
            conn.read_only = True
            views = tuple(
                self._view(
                    conn=conn,
                    oid=oid,
                    name=name,
                    comment=comment
                )
                for oid, name, comment in conn.execute(
                    query=_VIEWS,
                    params=(settings.SCHEMA,)
                ).fetchall()
            )
            categories = tuple(
                CategoryDoc(
                    name=name,
                    group_name=group_name
                )
                for name, group_name in conn.execute(query=_CATEGORIES).fetchall()
            )

        if not views:
            raise SchemaDocumentationError(f"no views found in schema {settings.SCHEMA!r}")
        return SemanticSchema(
            views=views,
            categories=categories
        )

    @staticmethod
    def _view(
            conn: Connection,
            oid: int,
            name: str,
            comment: str | None
    ) -> ViewDoc:
        if not comment:
            raise SchemaDocumentationError(f"view {name} has no COMMENT ON")

        columns = []
        for column_name, data_type, column_comment in conn.execute(
                query=_COLUMNS,
                params=(oid,)
        ).fetchall():
            if not column_comment:
                raise SchemaDocumentationError(f"column {name}.{column_name} has no COMMENT ON")
            columns.append(ColumnDoc(
                name=column_name,
                data_type=data_type,
                description=column_comment)
            )

        return ViewDoc(
            name=name,
            description=comment,
            columns=tuple(columns)
        )
