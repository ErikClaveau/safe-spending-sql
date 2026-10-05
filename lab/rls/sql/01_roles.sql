-- Roles and schema (run as the superuser `postgres`; nothing else uses it).
-- Idempotent: dropping the schema first lets the script run on a used database.
-- Role passwords equal the role names: lab only, localhost only, ephemeral data.

DROP SCHEMA IF EXISTS app CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_owner') THEN
        CREATE ROLE app_owner LOGIN PASSWORD 'app_owner';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_loader') THEN
        CREATE ROLE app_loader LOGIN PASSWORD 'app_loader';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_reader') THEN
        CREATE ROLE app_reader LOGIN PASSWORD 'app_reader';
    END IF;
END
$$;

-- Explicit attributes so a re-run also repairs a role that was tampered with.
ALTER ROLE app_owner  NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
ALTER ROLE app_loader NOSUPERUSER BYPASSRLS   NOCREATEROLE NOCREATEDB;
ALTER ROLE app_reader NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;

-- app_reader: read-only by default and bounded in time, set on the role itself (ADR-002).
ALTER ROLE app_reader SET default_transaction_read_only = on;
ALTER ROLE app_reader SET statement_timeout = '5s';

CREATE SCHEMA app AUTHORIZATION app_owner;

ALTER ROLE app_owner  SET search_path = app;
ALTER ROLE app_loader SET search_path = app;
ALTER ROLE app_reader SET search_path = app;
