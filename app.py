"""
Share of AI — Streamlit app
Interface for testing multiple LLMs in parallel on purchase recommendation queries.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    AVAILABLE_MODELS,
    AVAILABLE_TONES,
    AVAILABLE_LANGUAGES,
    DEFAULT_MODELS,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    SYSTEM_PROMPT_PATH,
    WEB_SEARCH_ENABLED,
    TAVILY_MONTHLY_LIMIT,
)
from core.client import ApolloClient
from core.prompt_builder import load_prompts, save_prompts, generate_prompt_via_llm, add_prompt
from core.runner import run_parallel, ModelResult

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Share of AI",
    page_icon="🐾",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_resource
def get_client() -> ApolloClient:
    return ApolloClient()


@st.cache_data
def get_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def results_to_df(results: list[ModelResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Prompt #": r.prompt_index,
            "Tone": r.tone or "",
            "Language": r.language or "",
            "Model": r.model,
            "Preferred Brand": r.preferred_brand,
            "Confidence": r.confidence,
            "Decision": r.decision,
            "Web Search": "🔍" if r.web_search_used else "",
            "Sources": len(r.search_results),
            "Latency (s)": r.latency_s,
            "OK": "✅" if r.success else "❌",
            "Error": r.error or r.schema_error or "",
        })
    return pd.DataFrame(rows)


def _tavily_usage_widget() -> None:
    """Renders the Tavily usage indicator in the sidebar."""
    from core.web_search import get_usage
    usage = get_usage()
    pct = usage["count"] / TAVILY_MONTHLY_LIMIT
    remaining = usage["remaining"]
    color = "normal" if pct < 0.75 else ("off" if pct < 0.90 else "inverse")
    st.sidebar.metric(
        label=f"🔍 Tavily usage ({usage['month']})",
        value=f"{usage['count']} / {TAVILY_MONTHLY_LIMIT}",
        delta=f"{remaining} remaining",
        delta_color=color,
    )
    st.sidebar.progress(min(pct, 1.0))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ Settings")

    st.subheader("Models")
    selected_models = st.multiselect(
        "Select models to test",
        options=AVAILABLE_MODELS,
        default=DEFAULT_MODELS,
    )

    st.subheader("LLM Parameters")
    temperature = st.slider("Temperature", 0.0, 1.0, DEFAULT_TEMPERATURE, 0.05)
    max_tokens = st.number_input("Max tokens", 500, 4000, DEFAULT_MAX_TOKENS, 100)

    st.subheader("🔍 Web Search")
    if WEB_SEARCH_ENABLED:
        use_web_search = st.toggle("Enable web search (Tavily)", value=False)
        if use_web_search:
            _tavily_usage_widget()
    else:
        st.info("Web search: coming in Phase 4")
        use_web_search = False

    st.divider()
    st.caption("Share of AI — Prototype v0.2")


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

st.title("🐾 Share of AI")
st.markdown(
    """
**Goal:** test multiple LLM models in parallel by simulating a user asking for veterinary
product purchase advice. Analyse which brands are preferred, with what confidence, and in which scenarios.
"""
)

tab_run, tab_prompts, tab_results = st.tabs(["▶️ Run Test", "📝 Prompts", "📊 Results"])


# ---------------------------------------------------------------------------
# Tab: Run Test
# ---------------------------------------------------------------------------

with tab_run:
    st.header("Run Test")

    if use_web_search:
        st.info("🔍 Web search enabled — the model will search Tavily before answering.", icon="ℹ️")

    prompts = load_prompts()

    col1, col2 = st.columns([2, 1])
    with col1:
        filter_tone = st.multiselect(
            "Filter by tone", options=AVAILABLE_TONES, default=[]
        )
        filter_lang = st.multiselect(
            "Filter by language", options=AVAILABLE_LANGUAGES, default=[]
        )

    with col2:
        st.metric("Total prompts", len(prompts))
        st.metric("Models selected", len(selected_models))
        st.metric(
            "Total calls",
            len([p for p in prompts
                 if (not filter_tone or p.get("tone") in filter_tone)
                 and (not filter_lang or p.get("language") in filter_lang)])
            * len(selected_models),
        )

    filtered = [
        p for p in prompts
        if (not filter_tone or p.get("tone") in filter_tone)
        and (not filter_lang or p.get("language") in filter_lang)
    ]

    with st.expander(f"Preview prompts ({len(filtered)} selected)"):
        for i, p in enumerate(filtered):
            st.markdown(f"**{i}** `[{p.get('tone','?')} / {p.get('language','?')}]` {p['prompt']}")

    if not selected_models:
        st.warning("Select at least one model in the sidebar.")
    elif not filtered:
        st.warning("No prompts match the current filters.")
    else:
        run_btn = st.button("🚀 Run", type="primary", use_container_width=True)
        if run_btn:
            client = get_client()
            system_prompt = get_system_prompt()

            with st.spinner(f"Running {len(filtered) * len(selected_models)} calls..."):
                results = run_parallel(
                    client=client,
                    system_prompt=system_prompt,
                    prompts=filtered,
                    models=selected_models,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_web_search=use_web_search,
                )

            st.session_state["last_results"] = results
            st.success(f"Done! {len(results)} results collected.")

            df = results_to_df(results)
            st.dataframe(df, use_container_width=True)

            st.subheader("Brand preference summary")
            brand_df = (
                df[df["OK"] == "✅"]
                .groupby(["Model", "Preferred Brand"])
                .size()
                .reset_index(name="Count")
                .sort_values(["Model", "Count"], ascending=[True, False])
            )
            st.dataframe(brand_df, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab: Prompts
# ---------------------------------------------------------------------------

with tab_prompts:
    st.header("Prompt Library")

    prompts = load_prompts()

    prompt_df = pd.DataFrame(prompts)
    st.dataframe(prompt_df, use_container_width=True, height=300)

    st.divider()
    st.subheader("Generate a new prompt")

    col_gen1, col_gen2, col_gen3 = st.columns(3)
    with col_gen1:
        gen_topic = st.text_input(
            "Topic",
            placeholder="e.g. flea prevention for a puppy",
        )
    with col_gen2:
        gen_tone = st.selectbox("Tone", AVAILABLE_TONES)
    with col_gen3:
        gen_lang = st.selectbox("Language", AVAILABLE_LANGUAGES)

    gen_model = st.selectbox(
        "Generator model",
        options=selected_models if selected_models else AVAILABLE_MODELS[:1],
        key="gen_model",
    )

    if st.button("✨ Generate prompt"):
        if not gen_topic.strip():
            st.warning("Enter a topic first.")
        else:
            client = get_client()
            with st.spinner("Generating..."):
                generated = generate_prompt_via_llm(
                    client=client,
                    topic=gen_topic,
                    tone=gen_tone,
                    language=gen_lang,
                    model=gen_model,
                )
            st.session_state["generated_prompt"] = generated

    if "generated_prompt" in st.session_state:
        st.text_area("Generated prompt", value=st.session_state["generated_prompt"], height=100)
        if st.button("💾 Save to library"):
            prompts = add_prompt(
                prompts,
                st.session_state["generated_prompt"],
                gen_tone,
                gen_lang,
            )
            save_prompts(prompts)
            st.success("Prompt saved!")
            del st.session_state["generated_prompt"]
            st.rerun()


# ---------------------------------------------------------------------------
# Tab: Results
# ---------------------------------------------------------------------------

with tab_results:
    st.header("Last Run Results")

    if "last_results" not in st.session_state:
        st.info("Run a test first.")
    else:
        results: list[ModelResult] = st.session_state["last_results"]
        df = results_to_df(results)

        model_filter = st.multiselect(
            "Filter by model",
            options=df["Model"].unique().tolist(),
            default=df["Model"].unique().tolist(),
        )
        filtered_df = df[df["Model"].isin(model_filter)]

        st.dataframe(filtered_df, use_container_width=True)

        st.subheader("Brand × Model heatmap (count)")
        ok_df = filtered_df[filtered_df["OK"] == "✅"]
        if not ok_df.empty:
            pivot = (
                ok_df.groupby(["Preferred Brand", "Model"])
                .size()
                .unstack(fill_value=0)
            )
            st.dataframe(pivot, use_container_width=True)

        st.subheader("Average confidence by model")
        if not ok_df.empty:
            conf_df = ok_df.groupby("Model")["Confidence"].mean().reset_index()
            conf_df.columns = ["Model", "Avg Confidence"]
            st.bar_chart(conf_df.set_index("Model"))
        else:
            st.info("No successful results to chart.")

        st.subheader("Response detail")
        selected_row = st.selectbox(
            "Select a result",
            options=range(len(results)),
            format_func=lambda i: f"#{i} — {results[i].model} | {results[i].preferred_brand} | {results[i].confidence}",
        )
        r = results[selected_row]
        st.markdown(f"**Model:** `{r.model}`")
        st.markdown(f"**Prompt:** {r.user_prompt}")

        if r.web_search_used and r.search_results:
            with st.expander(f"🔍 Web sources consulted ({len(r.search_results)})"):
                for src in r.search_results:
                    st.markdown(f"**[{src['title']}]({src['url']})**")
                    st.caption(src["snippet"][:300] + "..." if len(src["snippet"]) > 300 else src["snippet"])
                    st.divider()

        if r.parsed_json:
            st.json(r.parsed_json)
        elif r.error:
            st.error(r.error)
        else:
            st.code(r.raw_response or "")
