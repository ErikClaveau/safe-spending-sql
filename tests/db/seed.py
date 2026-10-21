"""Shared helpers to load small, hand-made datasets into the test database."""


def seed_base(conn):
    conn.execute("INSERT INTO categories VALUES (1, 'Supermercados', 'Alimentación')")
    conn.execute("INSERT INTO merchants VALUES (1, 'MERCADONA', '5411')")
    conn.execute("INSERT INTO users VALUES (1, 'Ana', 'Alicante', '2024-09-16')")
    conn.execute("INSERT INTO users VALUES (2, 'Beto', 'Madrid', '2024-09-16')")
    conn.execute("INSERT INTO accounts VALUES (10, 1, 'ES0000000000000000000010', 'EUR')")
    conn.execute("INSERT INTO accounts VALUES (11, 1, 'ES0000000000000000000011', 'EUR')")
    conn.execute("INSERT INTO accounts VALUES (20, 2, 'ES0000000000000000000020', 'EUR')")


def add_tx(conn, **overrides):
    row = {
        "tx_id": 1,
        "account_id": 10,
        "user_id": 1,
        "booking_date": "2026-09-01",
        "value_date": "2026-09-01",
        "amount": -42.50,
        "currency": "EUR",
        "exchange_rate": None,
        "amount_eur": -42.50,
        "description_raw": "COMPRA TARJ. 5402XXXX MERCADONA ALICANTE",
        "counterparty": None,
        "tx_code": "CARD_PURCHASE",
        "merchant_id": 1,
        "category_id": 1,
        "counterparty_account_id": None,
    }
    row.update(overrides)
    columns = ", ".join(row)
    placeholders = ", ".join(["%s"] * len(row))
    conn.execute(f"INSERT INTO transactions ({columns}) VALUES ({placeholders})", list(row.values()))
