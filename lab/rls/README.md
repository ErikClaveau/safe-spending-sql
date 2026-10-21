# RLS lab (ADR-002)

Disposable lab to validate the acceptance criteria of
`docs/adr/0002-aislamiento-entre-usuarios.md`. The role and policy scripts
will be reused in the real migration.

## Usage

```bash
docker compose -f lab/rls/docker-compose.yml up -d --wait
uv sync
uv run python lab/rls/lab_db.py   # (re)builds roles, schema and data; idempotent
uv run pytest lab/rls/tests       # the root `pytest` runs the real suite in tests/
docker compose -f lab/rls/docker-compose.yml down
```

Postgres listens on `127.0.0.1:5433` and its data lives in `tmpfs`: bringing
the container down wipes everything.

## Golden rule

Tests always connect as `app_owner`, `app_loader` or `app_reader`, never as
`postgres`: a superuser bypasses RLS, so the tests would pass without proving
anything. The superuser is only used to create roles and the schema.

## Layout

- `sql/`: scripts for roles, schema, policies and data, each run as the role that owns that step.
- `lab_db.py`: connection and build helpers shared by the scripts and the tests.
- `tests/`: pytest tests, one per acceptance criterion.
