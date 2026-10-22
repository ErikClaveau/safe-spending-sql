from enum import StrEnum


class ExecutionErrorKind(StrEnum):
    TIMEOUT = "timeout"
    DATABASE_ERROR = "database_error"
