-- Base tables, row level security and grants (docs/proyecto-1 section 6, ADR-002).
-- Runs as app_owner with search_path = app. Base tables are in English (ADR-005);
-- the Spanish semantic views arrive in a later migration.

-- Shared catalogs: no personal data, no RLS.
CREATE TABLE categories (
    category_id integer PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    group_name  text NOT NULL
);

-- Companies only. People (Bizum, transfers between individuals) go in
-- transactions.counterparty, which is protected by RLS (ADR-002).
CREATE TABLE merchants (
    merchant_id     integer PRIMARY KEY,
    normalized_name text NOT NULL UNIQUE,
    mcc             char(4) NOT NULL
);

CREATE TABLE users (
    user_id     integer PRIMARY KEY,
    name        text NOT NULL,
    city        text NOT NULL,
    signup_date date NOT NULL
);

-- All accounts are in euros (generator design; ADR-008 pending).
CREATE TABLE accounts (
    account_id integer PRIMARY KEY,
    user_id    integer NOT NULL REFERENCES users (user_id),
    iban       text NOT NULL,
    currency   char(3) NOT NULL DEFAULT 'EUR' CHECK (currency = 'EUR'),
    UNIQUE (account_id, user_id)
);

-- user_id is denormalised so the policy does not depend on a join with accounts.
-- The composite foreign keys keep it consistent with the owning account, and keep an
-- internal transfer's counterparty inside the same user's accounts.
CREATE TABLE transactions (
    tx_id                   bigint PRIMARY KEY,
    account_id              integer NOT NULL,
    user_id                 integer NOT NULL,
    booking_date            date NOT NULL,
    value_date              date NOT NULL,
    amount                  numeric(12, 2) NOT NULL,
    currency                char(3) NOT NULL,
    exchange_rate           numeric(12, 6) CHECK (exchange_rate > 0),
    amount_eur              numeric(12, 2) NOT NULL,
    description_raw         text NOT NULL,
    counterparty            text,
    tx_code                 text NOT NULL CHECK (tx_code IN (
        'CARD_PURCHASE', 'CARD_REFUND', 'DIRECT_DEBIT', 'TRANSFER_IN', 'TRANSFER_OUT',
        'BIZUM_IN', 'BIZUM_OUT', 'SALARY', 'FEE', 'ATM_WITHDRAWAL')),
    merchant_id             integer REFERENCES merchants (merchant_id),
    category_id             integer NOT NULL REFERENCES categories (category_id),
    counterparty_account_id integer,
    FOREIGN KEY (account_id, user_id) REFERENCES accounts (account_id, user_id),
    FOREIGN KEY (counterparty_account_id, user_id) REFERENCES accounts (account_id, user_id),
    -- The exchange rate is present exactly on foreign-currency operations.
    CHECK ((currency = 'EUR') = (exchange_rate IS NULL)),
    CHECK (counterparty_account_id IS DISTINCT FROM account_id)
);

CREATE INDEX transactions_user_booking_idx ON transactions (user_id, booking_date);

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

-- Grants are explicit per table (no default privileges), so a new table is never
-- readable by accident. With security_invoker views, Postgres checks the base tables
-- against app_reader, so it needs SELECT on them; the sqlglot allowlist, not the
-- GRANTs, keeps the LLM on the views (ADR-005).
GRANT USAGE ON SCHEMA app TO app_reader, app_loader;
GRANT SELECT ON categories, merchants, users, accounts, transactions TO app_reader;
GRANT INSERT ON categories, merchants, users, accounts, transactions TO app_loader;
