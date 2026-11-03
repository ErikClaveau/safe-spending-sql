# ADR-010: What to do with an ambiguous question

> 🇪🇸 Español: [../es/adr/0010-ambiguedad.md](../es/adr/0010-ambiguedad.md)

**Status:** Accepted, with points to revisit
**Date:** 2026-10-28
**Decides:** Erik Claveau
**Related:** ADR-006 (actions `query`, `clarify` and `refuse`), ADR-003 (evals)

## Context

Some questions do not fix what they ask: "How much did I spend on food?" does not say whether it is supermarkets, restaurants or the whole Alimentación group, or over what period. When no period is given, does the assistant ask or choose one?

The assistant has two exits: ask, or answer saying what it assumed. And today it **has no conversation**: `Assistant.ask(user_id, question)` is a call without history, so a clarifying question hands control back to the person, who has to write the whole question again.

## Decision

**Assume and state the assumption by default; ask only when there is no reasonable interpretation.**

- **There is a reasonable interpretation:** the query runs and the assumption is said in one sentence in `message` (for example, "You did not give a period: I use the whole history"). That assumption reaches the synthesizer as `assumptions` and the final answer mentions it.
  - With no period, the whole available history is used, with no date filter.
  - A vague category is resolved by the most likely interpretation, and which one is said.
- **There is none** (it is not known which movement is meant, or what to compare it with): `clarify` action, with **one** concrete question.
- **Refusing** is something else: a question outside the spending domain.

The rule lives in the SQL generator's prompt: "if it is enough to choose the most reasonable interpretation, do it with `query` and say so in `message` instead of asking".

**How it is evaluated.** The golden set marks these questions as `clarify` and accepts both behaviours: asking for the clarification, or answering by stating the assumption. Answering without saying anything is not valid. There are four questions (GS-074 to GS-077) and the `ambigua` category came out at 100 % in the latest measurement.

## Options considered

| Option | Experience | Evaluability | Risk |
|---|---|---|---|
| Always ask | A lost turn for every ambiguous question; today, also, the person repeats the whole question | Only that it asks can be checked | Tiring and unhelpful |
| Always assume | Immediate answer | Compared against a reference | A wrong figure the person does not notice, if the assumption is not stated |
| **Assume and state; ask only with no reasonable interpretation** | A useful answer in one turn | Evaluated against a reference, and the no-exit cases by behaviour | The "reasonable" criterion is set by the model |

## Consequences

**Easier**
- A useful answer in one turn, without needing conversation state.
- An answer with an assumption can be compared with a reference: dialogues need not be simulated to evaluate.
- The assumption stays in the assistant's result (`message`) and in the final text.

**Harder**
- The person may not read the assumption sentence and keep a figure that was not the one they wanted.
- "Reasonable" is not formalised and the boundary is blurry. The London trip shows it (GS-053 and GS-056): the reference answers with a period and the model sometimes asks for the dates; it is the only question whose behaviour changes between golden runs.
- Four questions are a small sample of the `ambigua` category.

**To revisit**
- With the API (week 5) there will be conversation: then `clarify` should keep the original question and be answered on the next turn. Not today.
- Extend the `ambigua` category when the golden set reaches 150-200 questions, with borderline cases like London's.
- Measure how often the model's assumption is not what the person wanted. With synthetic data and no users this cannot be measured; it is only known that the assumption is stated.

## Next steps

1. [x] Rule in the generator's prompt (default period and `clarify` with a single question).
2. [x] The assumption reaches the synthesizer and is mentioned in the answer.
3. [x] The golden set accepts asking for the clarification or stating the assumption.
4. [ ] More `ambigua` questions, with borderline cases.
5. [ ] Keep the original question when asking for clarification, once there is conversation.
