# ADR-004: A frontier model through an API behind the `LLMProvider` port

> 🇪🇸 Español: [../es/adr/0004-modelo-de-lenguaje.md](../es/adr/0004-modelo-de-lenguaje.md)

**Status:** Accepted
**Date:** 2026-10-21
**Decides:** Erik Claveau
**Related:** ADR-003 (evals), ADR-006 (LLM output)

## Context

The week 3 baseline sets the bar for quality, latency and cost. A reliable execution accuracy figure in Spanish over the semantic views is needed, not one capped by a small model. Project 3 (local or fine-tuned model) will use this baseline as its reference (plan §2.3).

## Decision

- The baseline uses a **frontier model through an API** (Claude), behind the `LLMProvider` port. The rest of the pipeline does not know the provider.
- The **specific model is configuration**, not code. For the baseline: `claude-sonnet-5-5`, as a balance between quality and cost. In week 5 `claude-haiku-5-5` and `claude-opus-5-5` are compared on the same golden set to publish the cost/quality ratio.
- Every trace and eval log records the exact model identifier, tokens and cost.
- Local models (Ollama) are outside this project's scope. The port allows adding them as an adapter.
- API keys are read from environment variables and never versioned. Only synthetic data is sent to the API.

## Options considered

| Option | Expected quality | Cost | Reproducibility | Baseline for project 3 |
|---|---|---|---|---|
| **Frontier through an API** | High | Per token | Depends on the model version | Yes |
| Local (Ollama) | Lower in Spanish and SQL | None per query | High | Mixes two variables |
| Two models from the start | High | Per token, double | Medium | Yes, richer |

## Consequences

**Easier**
- A representative baseline with little deployment effort.
- Changing model is a configuration change, measurable with the same evals.

**Harder**
- Cost and latency depend on a third party. Full runs cost money, so CI uses the smoke subset.
- Model aliases can change: the exact version must be pinned in each experiment.
- Reproducibility is statistical, not bit for bit. `claude-sonnet-5-5` rejects `temperature`, `top_p` and `top_k` other than the default, so variation is controlled only by pinning the model and `effort`, which is set explicitly in the configuration (adapter: `medium` by default).
- The provider's automatic alternative on a safety refusal is on (`fallbacks: "default"`). If it triggers, the model that answered is not the requested one: `LLMResponse.model` records it and the cost is computed with the price of the model that answered. It can be turned off by configuration for a clean measurement.

**Comparison result (2026-10-28)**
- Full golden set v0, same prompt and effort: Haiku 84.4 %, Sonnet 91.1 %, Opus 90.0 % tolerant accuracy, at $0.9, $13.2 and $29.8 per 1,000 queries (detail in `docs/iteraciones-evals.md`).
- Second comparison (2026-10-29), with 152 questions, prompt v4 and corrected references: Sonnet 98.0 % ($13.6 per 1,000 queries), Haiku 89.5 % and 88.8 % in two runs ($1.1). Haiku is 9 points below, with format failures (`generation_failed`) and the occasional wrong figure that looks right; its security gates give 0. **Sonnet 5.5** is kept; Haiku stays as a documented low-cost alternative.
- Opus does not justify double the cost and Haiku loses 6 points, including a case where it answers where it should refuse. **Sonnet 5.5** is kept. One run per model: differences of 1-2 points between Sonnet and Opus are not conclusive.

**To revisit**
- If the cost of full evals turns out high, run the full set only nightly or by hand.

## Next steps

1. [ ] `LLMProvider` adapter for the Claude API, with tokens and cost in the response.
2. [ ] Model and parameters in the configuration, and their recording in `TraceSink`.
3. [x] Measure the base model's cost per 1,000 queries (plan §2.3): $13.2 with Sonnet 5.5, without answer synthesis.
