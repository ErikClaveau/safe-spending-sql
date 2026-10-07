"""Table names shared by the generator (which writes them) and the loader (which reads them).

Single source of truth for which tables exist and where they go. Neutral on purpose: the
loader must not import the generator and the generator must not import the database layer.
"""

# What a real bank would have; loaded into Postgres. Foreign-key order: parents first.
OPERATIONAL = ("categories", "merchants", "users", "accounts", "transactions")

# Ground-truth labels for the evals. Never loaded into the application database.
LABELS = ("tx_labels", "user_labels", "scenarios")
