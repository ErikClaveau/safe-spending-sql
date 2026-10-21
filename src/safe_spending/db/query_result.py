"""The value returned by `run_as_user`."""

from pydantic import BaseModel, ConfigDict, Field


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    truncated: bool = Field(description="the query returned more than `max_rows`; the rest were discarded")
