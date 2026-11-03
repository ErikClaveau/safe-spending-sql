# ADR-006: Structured output with tool use and Pydantic validation

> 🇪🇸 Español: [../es/adr/0006-salida-estructurada.md](../es/adr/0006-salida-estructurada.md)

**Status:** Accepted
**Date:** 2026-10-21
**Decides:** Erik Claveau
**Related:** ADR-004 (model), ADR-005 (semantic layer)

## Context

The pipeline needs the model to return data, not prose: the SQL, whether to ask for clarification, whether the question is out of domain. A malformed output must not reach the validator or the executor. Also every attempt (failed ones included) must be in the trace (plan §10).

## Decision

- The model answers through **tool use** with a JSON schema that forces it to fill typed fields (for example `accion` ∈ {`consultar`, `aclarar`, `rechazar`}, `sql`, `mensaje`). The field names and values are Spanish identifiers in the code and are kept as they are.
- The tool is declared with `strict: true`, so if the model calls it, the input meets the schema. **The call cannot be forced** (`tool_choice` `any`/`tool` returns a 400 on `claude-sonnet-5-5` and `claude-opus-5-5`): `auto` is used and the system asks to answer only with the tool. A response without a call arrives as `structured_output = None` and counts as a failed attempt, like an input that does not validate.
- The response is **validated with Pydantic**. If it does not validate, it counts as a failed attempt and is recorded; the number of retries is configurable and bounded.
- The SQL that comes out of this step is still untrusted text: it goes through sqlglot and runs under RLS (ADR-002). Pydantic validates shape, never security.
- The Pydantic models are the contract of the `SQLGenerator` port, independent of the provider. Tool-use details stay in the `LLMProvider` adapter.
- The numbers in the final answer are computed by the SQL, not by the model (a project invariant).

## Options considered

| Option | Robustness | Traceability | Dependencies | Retry control |
|---|---|---|---|---|
| **Tool use + Pydantic** | High: schema enforced by the provider | High: raw JSON and validation errors | None extra | Own |
| Instructor | High | Medium: hides part of the attempts | One more | Delegated |
| Text with parsing | Low | Medium | None | Own |

## Consequences

**Easier**
- Typed outputs and format failures that are visible and measurable as an error category.
- Each attempt stays in the trace as it is.

**Harder**
- Each provider's adapter must translate the schema to its tool-use mechanism.
- Retries and their recording must be implemented.

**To revisit**
- The `aclarar` action is used only when there is no reasonable interpretation; if there is one, it is assumed and stated (ADR-010).

- The `GeneratorResponse` schema (optional fields with a null `anyOf` and `$defs` for the enum) was tested on 2026-10-21 against the real API with `strict: true` and `claude-sonnet-5-5`: the API accepted it and the model called the tool on both test questions (one query and one out of domain), with outputs that validated with Pydantic.

## Next steps

1. [ ] Pydantic models of the generator's response.
2. [ ] Retries with each attempt recorded in the trace.
3. [ ] Count format failures separately from SQL failures in the evals.
