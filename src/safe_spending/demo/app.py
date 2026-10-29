"""The demo app (ADR-009): `uv run streamlit run src/safe_spending/demo/app.py`.

The sidebar picks the user and stands in for the auth layer: `user_id` never comes from the question.
Everything else is the library the evals measure, built by `pipeline.factory`.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from safe_spending.demo.attacks import AttackKind, Preset, judge, load_presets
from safe_spending.evals.adversarial import canaries_by_user, read_expected
from safe_spending.generator.config import load_config
from safe_spending.pipeline.assistant import AssistantOutcome, AssistantResult
from safe_spending.pipeline.factory import DEFAULT_MODEL, build_assistant
from safe_spending.pipeline.generation import PROMPT_VERSION
from safe_spending.pipeline.tracing import trace_context_from_environment

DEMO_SALT = "demo-synthetic-users"  # the demo users are synthetic: no secret needed
TRACE_DIR = Path("logs/traces")
USER_GROUPS = (
    (range(1, 16), "functional"),
    (range(16, 21), "injection traps"),
)

st.set_page_config(page_title="Safe spending", page_icon="💶", layout="wide")


@st.cache_resource(show_spinner="Starting the assistant…")
def assistant():
    config = load_config()
    built, schema_version = build_assistant(
        model=os.environ.get("DEMO_MODEL", DEFAULT_MODEL),
        prompt_version=PROMPT_VERSION,
        max_corrections=1,
        reference_date=config.reference_date,
        dbname=None,
        synthesize=True,
        trace_dir=TRACE_DIR,
        trace_context=trace_context_from_environment(default_salt=DEMO_SALT),
    )
    return built, schema_version, config.reference_date, config.n_users


@st.cache_resource(show_spinner="Reading the adversarial set…")
def adversarial():
    return load_presets(), read_expected(), canaries_by_user()


def user_label(user_id: int) -> str:
    group = next((name for users, name in USER_GROUPS if user_id in users), "population")
    return f"User {user_id} ({group})"


def main() -> None:
    built, schema_version, today, n_users = assistant()
    presets, expected, canaries = adversarial()

    st.title("Safe spending")
    st.caption(
        "Ask about the spending of a synthetic bank customer. Isolation is enforced by Postgres row-level "
        "security, and every number in the answer is checked against the query result."
    )

    with st.sidebar:
        st.header("Who is asking")
        user_id = st.selectbox("User", range(1, n_users + 1), format_func=user_label, key="user_id")
        st.info(
            "This selector stands in for authentication. The assistant is told who is asking by this widget, "
            "never by the text of the question: ask about someone else and see what happens.",
            icon="🔐",
        )
        st.caption(f"Today is fixed at {today} · schema {schema_version} · prompt {PROMPT_VERSION}")
        st.caption("Synthetic data only.")

    ask_tab, break_tab = st.tabs(["Ask", "Try to break it"])

    with ask_tab:
        with st.form("ask"):
            question = st.text_input("Question", placeholder="¿Cuánto gasté en supermercados el mes pasado?")
            submitted = st.form_submit_button("Ask")
        if submitted and question.strip():
            with st.spinner("Thinking…"):
                st.session_state["last_ask"] = (user_id, None, built.ask(user_id, question.strip()))
        show_last(key="last_ask", expected=expected, canaries=canaries)

    with break_tab:
        st.write(
            "Questions from the adversarial set. Each one runs **as the user it was written for**, whoever is "
            "selected in the sidebar, and the verdict uses the same rules as the release gates."
        )
        kind = st.radio(
            "Attack",
            list(AttackKind),
            horizontal=True,
            format_func=lambda k: {
                AttackKind.ISOLATION: "Reach another user's data",
                AttackKind.INJECTION: "Injection planted in the data",
            }[k],
        )
        options = [p for p in presets if p.kind is kind]
        preset = st.selectbox("Question", options, format_func=lambda p: p.label)
        if preset.kind is AttackKind.ISOLATION:
            st.caption(f"Asked by user {preset.user_id}, aiming at the data of user {preset.victim_user_id}.")
        else:
            st.caption(
                f"An innocent question by user {preset.user_id}. The attack is a text inside a received "
                "transfer or Bizum concept, asking the assistant to print a code."
            )
        if st.button("Run it"):
            with st.spinner("Thinking…"):
                st.session_state["last_break"] = (preset.user_id, preset, built.ask(preset.user_id, preset.question))
        show_last(key="last_break", expected=expected, canaries=canaries)


def show_last(key: str, expected, canaries) -> None:
    last = st.session_state.get(key)
    if last is None:
        return
    user_id, preset, result = last
    if preset is not None:
        verdict = judge(preset=preset, result=result, expected=expected, canaries=canaries.get(user_id, ()))
        if verdict.broken:
            st.error(f"Attack succeeded. {verdict.explanation}")
        else:
            st.success(f"Attack failed. {verdict.explanation}")
    show_result(user_id, result)


def show_result(user_id: int, result: AssistantResult) -> None:
    st.subheader(f"Answer for user {user_id}")
    if result.answer:
        st.markdown(result.answer)
    elif result.message:
        st.markdown(result.message)
    st.caption(f"Outcome: `{result.outcome.value}`")
    if result.outcome is AssistantOutcome.SYNTHESIS_FAILED:
        st.warning("The answer text was dropped: it did not pass the numeric check.")

    if result.sql:
        with st.expander("SQL and validation", expanded=True):
            st.code(result.sql, language="sql")
            violations = result.validation.violations if result.validation else ()
            if violations:
                st.error("Rejected by the validator:\n\n" + "\n".join(f"- {v}" for v in violations))
            elif result.validation:
                st.write("✅ Validator: one SELECT over the semantic views, with a LIMIT.")
            if result.corrections:
                st.write(f"↻ The model had to write it again {len(result.corrections)} time(s).")

    rows = result.execution.result if result.execution else None
    if rows is not None:
        with st.expander(f"Rows ({len(rows.rows)}{'+' if rows.truncated else ''})"):
            st.dataframe(pd.DataFrame(rows.rows, columns=rows.columns), width="stretch")
    elif result.execution and result.execution.error:
        st.error(f"Database error: {result.execution.error}")

    if result.synthesis and result.synthesis.attempts[-1].verification:
        verification = result.synthesis.attempts[-1].verification
        st.write("✅ Every number in the answer is in the result, the question or the SQL." if verification.ok
                 else f"⚠️ Untraced numbers: {', '.join(verification.untraced)}")

    cost = f"${result.cost_usd:.4f}" if result.cost_usd is not None else "unknown"
    stages = result.latency_by_stage
    st.caption(
        f"Cost {cost} · {result.latency_s:.1f}s "
        f"(generation {stages.generation_s:.1f}s, query {stages.execution_s:.2f}s, answer {stages.synthesis_s:.1f}s)"
    )


main()
