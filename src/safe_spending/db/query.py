"""Run a query as one user, the way the API's executor will (ADR-002).

The query is never rewritten and never gets a user filter: isolation is Postgres RLS. The
function opens a read-only transaction as `app_reader`, sets the user with a transaction-local
`set_config` as its first statement, checks that it took, and only then runs the SQL as it is.

The user id is an `int` that comes from the authentication layer. It is never taken from the
question or from what a model wrote, which is why anything else is refused before the database.
"""

from safe_spending.db import settings
from safe_spending.db.exceptions import IdentityNotSetError
from safe_spending.db.query_result import QueryResult

DEFAULT_MAX_ROWS = 1000


def run_as_user(
        user_id: int,
        sql: str,
        *,
        dbname: str | None = None,
        max_rows: int = DEFAULT_MAX_ROWS
) -> QueryResult:
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        raise TypeError(f"user_id must be an int from the authentication layer, not {user_id!r}")

    with settings.connect(
            role=settings.APP_READER,
            dbname=dbname
    ) as conn:
        conn.read_only = True  # BEGIN READ ONLY, a second layer behind the GRANTs
        conn.execute(
            query="SELECT set_config('app.user_id', %s, true)",
            params=(str(user_id),)
        )

        confirmed = conn.execute(query="SELECT current_setting('app.user_id', true)").fetchone()[0]
        if confirmed != str(user_id):
            raise IdentityNotSetError(f"expected app.user_id = {user_id}, found {confirmed!r}")

        cursor = conn.execute(query=sql)
        columns = tuple(column.name for column in cursor.description)
        rows = cursor.fetchmany(size=max_rows + 1)

    return QueryResult(
        columns=columns,
        rows=tuple(tuple(row) for row in rows[:max_rows]),
        truncated=len(rows) > max_rows,
    )
