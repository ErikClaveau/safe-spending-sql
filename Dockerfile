# One image for the setup job (roles, migrations, dataset load) and the Streamlit demo (ADR-009).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --extra demo --no-install-project

# The package resolves `evals/` and `dataset/` relative to the source tree, so they travel with it.
COPY alembic.ini ./
COPY src ./src
COPY evals ./evals
COPY dataset ./dataset
RUN uv sync --locked --no-dev --extra demo

EXPOSE 8501
CMD ["streamlit", "run", "src/safe_spending/demo/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
