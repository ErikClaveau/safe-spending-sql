-- Tables, RLS policies, views and grants (run as `app_owner`).
-- Mirrors the shape defined in ADR-002; money and dates are simplified for the lab.

CREATE TABLE users (
    user_id integer PRIMARY KEY,
    name    text NOT NULL
);

CREATE TABLE accounts (
    account_id integer PRIMARY KEY,
    user_id    integer NOT NULL REFERENCES users (user_id),
    iban       text NOT NULL,
    UNIQUE (account_id, user_id)
);

-- user_id is denormalised so the policy does not depend on a join with accounts.
-- The composite foreign key keeps it consistent with the owning account.
CREATE TABLE transactions (
    tx_id        integer PRIMARY KEY,
    account_id   integer NOT NULL,
    user_id      integer NOT NULL,
    booking_date date NOT NULL,
    amount       numeric(12, 2) NOT NULL,
    description  text NOT NULL,
    FOREIGN KEY (account_id, user_id) REFERENCES accounts (account_id, user_id)
);

-- Same policy shape on every table with user data. Fails closed: with the variable
-- unset or empty, NULLIF yields NULL and the comparison is never true.
ALTER TABLE users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE users        FORCE  ROW LEVEL SECURITY;
ALTER TABLE accounts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts     FORCE  ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions FORCE  ROW LEVEL SECURITY;

CREATE POLICY aislamiento_usuario ON users
    FOR SELECT TO app_reader
    USING (user_id = NULLIF(current_setting('app.user_id', true), '')::int);

CREATE POLICY aislamiento_usuario ON accounts
    FOR SELECT TO app_reader
    USING (user_id = NULLIF(current_setting('app.user_id', true), '')::int);

CREATE POLICY aislamiento_usuario ON transactions
    FOR SELECT TO app_reader
    USING (user_id = NULLIF(current_setting('app.user_id', true), '')::int);

-- Semantic view as the LLM would see it: no user_id column (ADR-005).
CREATE VIEW v_movimientos WITH (security_invoker = true) AS
    SELECT tx_id, account_id, booking_date, amount, description
    FROM transactions;

-- Grants. With security_invoker, Postgres checks the base tables against app_reader,
-- so it needs SELECT on them too: only the sqlglot allowlist keeps the LLM on views.
GRANT USAGE ON SCHEMA app TO app_reader, app_loader;
GRANT SELECT ON users, accounts, transactions TO app_reader;
GRANT SELECT ON v_movimientos TO app_reader;
GRANT INSERT ON users, accounts, transactions TO app_loader;
