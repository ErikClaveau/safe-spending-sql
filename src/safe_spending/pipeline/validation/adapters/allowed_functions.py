"""The functions the assistant's SQL may call: an allowlist, because a blocklist is always one name behind.

A blocklist stopped `dblink` and not `dblink_exec`, and let through `query_to_xml('SELECT ...')`, which runs
text as SQL and so goes around the list of views. Anything not named here is rejected, whatever it does.

The names are the ones sqlglot gives the function, not the ones Postgres uses: `string_agg` is `group_concat`,
`ceiling` is `ceil`, `date_trunc` is `timestamp_trunc`, `to_char` is `time_to_str`. A test runs every entry
through the validator so a sqlglot upgrade that renames one fails there, not in front of a user.

Every function below is pure: no clock, no session state, no files, no locks, no text run as SQL. The set is
what the assistant has written in practice (all the SQL in the eval logs) plus close neighbours that are as
harmless. `current_date` and `now()` are left out on purpose: the assistant is told today's date and must
write it, since the result has to match the frozen date of the data. To allow a function, add it and a
snippet to `tests/pipeline/test_validator_functions.py`.
"""

AGGREGATES = frozenset({
    "sum", "count", "avg", "min", "max",
    "stddev", "stddev_pop", "stddev_samp", "variance", "variance_pop",
    "logical_and", "logical_or",  # bool_and, bool_or
    "array_agg", "group_concat",  # string_agg
    "percentile_cont", "percentile_disc", "mode",
})

SCALARS = frozenset({
    "coalesce", "nullif", "greatest", "least",
    "abs", "round", "ceil", "floor", "trunc", "sign", "power", "sqrt", "ln", "exp",
    "length", "lower", "upper", "initcap", "trim", "substring", "replace", "concat", "concat_ws", "left", "right",
    "split_part",
})

DATES_AND_TYPES = frozenset({
    "timestamp_trunc",  # date_trunc
    "time_to_str",  # to_char
    "extract",  # extract and date_part
    "str_to_date",  # to_date
    "make_date", "age",  # sqlglot does not type these two
    "cast",  # x::date, CAST(x AS numeric), date '2026-01-01'
    "exploding_generate_series",  # generate_series in the select list: the assistant uses it for a month spine
})

WINDOWS = frozenset({
    "row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value", "ntile",
})

CONDITIONALS_AND_OPERATORS = frozenset({
    "case", "if", "exists",
    "and", "or",  # sqlglot builds them as functions
    "regexp_like", "regexp_i_like",  # ~ and ~*
})

ALLOWED_FUNCTIONS = AGGREGATES | SCALARS | DATES_AND_TYPES | WINDOWS | CONDITIONALS_AND_OPERATORS
