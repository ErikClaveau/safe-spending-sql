# ADR-007: Observability with a `TraceSink` port and file traces first

> 🇪🇸 Español: [../es/adr/0007-observabilidad.md](../es/adr/0007-observabilidad.md)

**Status:** Accepted
**Date:** 2026-10-28
**Decides:** Erik Claveau
**Related:** ADR-003 (evals), ADR-004 (model), ADR-006 (LLM output), plan §10

## Context

The plan (§10) asks for one trace per request with: request identifier, user (pseudonym), commit, model, prompt and schema versions, SQL of all attempts, validation result, rows returned, latency per stage, tokens and cost, and numeric verification result. The plan's base is self-hosted Langfuse; the alternative, OpenTelemetry with Phoenix. The ADR has been pending since the plan.

**What already exists.** `Assistant.ask` returns an `AssistantResult`: an immutable Pydantic model with the question, the result of each stage (generation, validation, execution, synthesis), earlier attempts in `corrections`, and total cost and latency. It is already the trace of one request. The Inspect logs store that whole object in `assistant_result` per sample, and that is today the only place to look at why a question failed. What is missing is the `TraceSink` port (plan §8), the request identifier, the commit and the per-stage latency of generation and synthesis (they are summed, not broken down).

**Project constraints**
- "`docker compose up` starts everything" is part of the definition of done (plan §15). Every extra service weighs on startup and CI.
- A trace contains result rows and third-party concepts (untrusted text, with the injection traps). They are synthetic data, but the trace must not be a path for data leakage between users or for canaries towards a system someone could read as instructions.
- The evals (ADR-003) already store their traces; the API's observability is a different use (debugging a real request) and cannot be a condition of the evals.

## Decision

1. **The `TraceSink` port is created** with a single method `emit(trace)`, where `trace` is the `AssistantResult` plus the request metadata (`request_id`, pseudonymised `user_id`, `commit_sha`, model, prompt and schema versions). The `Assistant` receives it optionally, like the synthesizer; with no sink, nothing changes.
2. **First adapter: a local JSONL file** (one line per request, in `logs/traces/`, outside git). No dependencies or services, it works in tests and CI, and covers all the plan's fields.
3. **Second adapter, optional and for later: OpenTelemetry to Phoenix**, with one span per stage (generation, validation, execution, synthesis, numeric verification) and the attributes in OpenTelemetry's GenAI semantic schema. Phoenix runs in a single container, as one more Docker Compose service under a profile (`--profile observability`), not required for `docker compose up`.
4. **Langfuse is discarded for this project**, not forever: the port allows adding it as an adapter.
5. **Trace content rules**: the `user_id` is stored as a pseudonym (hash with a configuration salt), not the number; result rows are stored in full only in the local file adapter; the OpenTelemetry adapter exports aggregate figures (number of rows, columns, SQL, status of each stage) but not the content of the cells.

## Options considered

| Option | Startup | Covers plan §10 | Fit with the evals | Risk |
|---|---|---|---|---|
| Self-hosted Langfuse | Heavy: per its documentation, version 3 asks for Postgres, ClickHouse, Redis and S3 storage (to verify when implementing) | Yes, with its own interface | Good (datasets and scores) | A lot of infrastructure for a six-week project; competes with a simple `docker compose up` |
| OpenTelemetry + Phoenix | One container | Yes, through span attributes | Good | The GenAI schema attributes change; pin the version |
| OpenTelemetry without an interface | None, but a destination is needed to read the traces | Yes | Fair | Without a viewer, not very visible in a portfolio |
| **Port + JSONL, with optional Phoenix** | None by default | Yes | Direct: the same object the Inspect logs already store | Two adapters to maintain |

## Consequences

**Easier**
- Debugging a request without calling the model again: the whole path is on one line of the file.
- The adapter's tests need no network or services. Changing destination is an adapter.
- `docker compose up` stays light.

**Harder**
- Per-stage latency: solved with `AssistantResult.latency_by_stage` (`StageLatency`: generation, execution and synthesis, summed over all attempts; `latency_s` is their total). Validation is not measured (sqlglot takes far less than a millisecond) and numeric verification counts inside synthesis.
- The user pseudonym needs a salt in configuration and a rotation rule.
- A JSONL file grows without limit: rotation by day and a maximum size.

**To revisit**
- If the debugging volume grows, look at Langfuse as a third adapter.
- If Phoenix adds nothing over the file in the demo (ADR-009), it is not kept.

## Next steps

1. [x] `TraceSink` port and `RequestTrace` and `TraceContext` models (trace + metadata), in `pipeline/assistant/` because the `Assistant` defines and consumes them; the adapters live in `pipeline/tracing/`.
2. [x] JSONL adapter, with a test that checks the `user_id` does not reach the file and that the line holds the full result. The line is not loaded back into the model: it includes computed fields (cost, latency, SQL), which the model rejects on input. It is for reading, not for reconstructing.
3. [x] `Assistant` receives `trace_sink` and `trace_context` (together); adds `request_id` and the pseudonym; a failing sink is logged and does not change the answer. The `commit_sha` comes from `COMMIT_SHA` or git (with `-dirty` if there are uncommitted changes) and the salt from `TRACE_USER_SALT` (`pipeline/tracing/trace_context.py`). The Inspect tasks already trace to `logs/traces/` with a fixed salt, because their users are synthetic; the API, which does not exist yet, will have to require the variable.
4. [ ] OpenTelemetry/Phoenix adapter and Docker Compose profile (optional, only if time remains after the demo).
5. [x] Plan §12, §11 and changelog updated.
