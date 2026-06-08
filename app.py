"""
Share of AI — Streamlit app
Interface for testing multiple LLMs in parallel on purchase recommendation queries.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from config import (
    AVAILABLE_MODELS,
    AVAILABLE_TONES,
    AVAILABLE_LANGUAGES,
    AVAILABLE_CATEGORIES,
    DEFAULT_MODELS,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    SYSTEM_PROMPT_PATH,
    WEB_SEARCH_ENABLED,
    TAVILY_MONTHLY_LIMIT,
)
from core.client import ApolloClient
from core.prompt_builder import load_prompts, save_prompts, generate_prompt_via_llm, generate_prompts_batch_via_llm, add_prompt
from core.runner import run_parallel, ModelResult
from core.brand_groups import load_brand_groups, save_brand_groups, normalize_brands_in_df

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Share of AI",
    page_icon="🐾",
    layout="wide",
)

st.markdown("""
<style>
/* Metric value */
[data-testid="stMetricValue"] { color: #00E47C; }

/* Dataframe header */
[data-testid="stDataFrameResizable"] thead tr th {
    background-color: #0D3D2E;
    color: #00E47C;
}

/* Expander header */
[data-testid="stExpander"] summary {
    color: #00E47C;
}

/* Sidebar title */
[data-testid="stSidebarContent"] h2 {
    color: #00E47C;
}

/* Success/info banner accent */
[data-testid="stAlert"] { border-left-color: #00E47C; }

/* Tab active underline */
[data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: #00E47C !important;
    color: #00E47C !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_resource
def get_client() -> ApolloClient:
    return ApolloClient()


@st.cache_data
def get_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.error(f"System prompt not found: {SYSTEM_PROMPT_PATH}. Add the file and restart.")
        st.stop()


def json_to_results(raw: str) -> list[ModelResult]:
    import dataclasses
    from datetime import datetime as dt
    valid_keys = {f.name for f in dataclasses.fields(ModelResult)}
    rows = json.loads(raw)
    results = []
    for d in rows:
        d["timestamp"] = dt.fromisoformat(d["timestamp"])
        results.append(ModelResult(**{k: v for k, v in d.items() if k in valid_keys}))
    return results


def results_to_json(results: list[ModelResult]) -> str:
    import dataclasses

    class _Encoder(json.JSONEncoder):
        def default(self, o):
            try:
                return vars(o)
            except TypeError:
                return str(o)

    rows = []
    for r in results:
        d = dataclasses.asdict(r)
        d["timestamp"] = r.timestamp.isoformat()
        rows.append(d)
    return json.dumps(rows, cls=_Encoder, ensure_ascii=False, indent=2)


def _download_buttons(results: list[ModelResult], df: pd.DataFrame, key_suffix: str) -> None:
    ts = results[0].timestamp.strftime("%Y%m%d_%H%M%S") if results else "run"
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇️ Download CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"shareofai_{ts}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_csv_{key_suffix}",
        )
    with col2:
        st.download_button(
            label="⬇️ Download JSON",
            data=results_to_json(results).encode("utf-8"),
            file_name=f"shareofai_{ts}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{key_suffix}",
        )


def results_to_df(results: list[ModelResult], brand_groups: list[dict] | None = None) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Prompt #": r.prompt_index,
            "Category": r.category or "",
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
            "Error": r.error or r.schema_error or r.json_parse_error or "",
        })
    df = pd.DataFrame(rows)
    if brand_groups:
        normalize_brands_in_df(df, brand_groups)
    return df


def _grouped_bar(data: pd.DataFrame, x: str, color: str, y: str = "Count", facet: str | None = None):
    """Altair grouped (side-by-side) bar chart. Optionally faceted by a column."""
    import altair as alt
    base = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(f"{x}:N", title=x, axis=alt.Axis(labelAngle=-30)),
            xOffset=alt.XOffset(f"{color}:N"),
            y=alt.Y(f"{y}:Q", title=y),
            color=alt.Color(f"{color}:N"),
            tooltip=[x, color, y],
        )
    )
    if facet:
        return (
            base.facet(column=alt.Column(f"{facet}:N", title=facet))
            .resolve_scale(x="independent")
        )
    return base.properties(height=300)


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

tab_run, tab_prompts, tab_results, tab_brands, tab_content, tab_source_eval = st.tabs(["▶️ Run Test", "📝 Prompts", "📊 Results", "🏷️ Brand Groups", "🔬 Content Analysis", "🧭 Source Evaluation"])

brand_groups = load_brand_groups()


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
        all_categories = sorted({p.get("category", "") for p in prompts if p.get("category")})
        filter_cat = st.multiselect(
            "Filter by category", options=all_categories, default=[]
        )

    with col2:
        st.metric("Total prompts", len(prompts))
        st.metric("Models selected", len(selected_models))
        st.metric(
            "Total calls",
            len([p for p in prompts
                 if (not filter_tone or p.get("tone") in filter_tone)
                 and (not filter_lang or p.get("language") in filter_lang)
                 and (not filter_cat or p.get("category") in filter_cat)])
            * len(selected_models),
        )

    filtered = [
        p for p in prompts
        if (not filter_tone or p.get("tone") in filter_tone)
        and (not filter_lang or p.get("language") in filter_lang)
        and (not filter_cat or p.get("category") in filter_cat)
    ]

    with st.expander(f"Preview prompts ({len(filtered)} selected)"):
        for i, p in enumerate(filtered):
            cat = p.get("category", "")
            cat_label = f" / {cat}" if cat else ""
            st.markdown(f"**{i}** `[{p.get('tone','?')} / {p.get('language','?')}{cat_label}]` {p['prompt']}")

    if not selected_models:
        st.warning("Select at least one model in the sidebar.")
    elif not filtered:
        st.warning("No prompts match the current filters.")
    else:
        run_btn = st.button("🚀 Run", type="primary", use_container_width=True)
        if run_btn:
            client = get_client()
            system_prompt = get_system_prompt().replace("{max_tokens}", str(max_tokens - 200))

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

            df = results_to_df(results, brand_groups)
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

            st.subheader("💾 Save results")
            _download_buttons(results, df, key_suffix="run")

            web_results = [r for r in results if r.web_search_used and r.search_results]
            if web_results:
                st.subheader("🔍 Web sources consulted")
                for r in web_results:
                    label = f"#{r.prompt_index} — {r.model} ({len(r.search_results)} sources)"
                    with st.expander(label):
                        for src in r.search_results:
                            st.markdown(f"**[{src['title']}]({src['url']})**")
                            snippet = src["snippet"]
                            st.caption(snippet[:300] + "..." if len(snippet) > 300 else snippet)
                            st.divider()


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

    col_gen1, col_gen2, col_gen3, col_gen4 = st.columns(4)
    with col_gen1:
        gen_topic = st.text_input(
            "Topic",
            placeholder="e.g. flea prevention for a puppy",
        )
    with col_gen2:
        gen_tone = st.selectbox("Tone", AVAILABLE_TONES)
    with col_gen3:
        gen_lang = st.selectbox("Language", AVAILABLE_LANGUAGES)
    with col_gen4:
        gen_cat = st.selectbox("Category", ["(none)"] + AVAILABLE_CATEGORIES)

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
            try:
                with st.spinner("Generating..."):
                    generated = generate_prompt_via_llm(
                        client=client,
                        topic=gen_topic,
                        tone=gen_tone,
                        language=gen_lang,
                        model=gen_model,
                    )
                st.session_state["generated_prompt"] = generated
            except Exception as exc:
                st.error(f"Generation failed: {exc}")

    if "generated_prompt" in st.session_state:
        st.text_area("Generated prompt", value=st.session_state["generated_prompt"], height=100)
        if st.button("💾 Save to library"):
            prompts = add_prompt(
                prompts,
                st.session_state["generated_prompt"],
                gen_tone,
                gen_lang,
                category=gen_cat if gen_cat != "(none)" else None,
            )
            save_prompts(prompts)
            st.success("Prompt saved!")
            del st.session_state["generated_prompt"]
            st.rerun()

    st.divider()
    st.subheader("Generate a batch of prompts")

    col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
    with col_b1:
        batch_topic = st.text_input(
            "Topic",
            placeholder="e.g. flea prevention for a puppy",
            key="batch_topic",
        )
    with col_b2:
        batch_tones = st.multiselect("Tones", AVAILABLE_TONES, default=AVAILABLE_TONES[:2], key="batch_tones")
    with col_b3:
        batch_langs = st.multiselect("Languages", AVAILABLE_LANGUAGES, default=AVAILABLE_LANGUAGES[:2], key="batch_langs")
    with col_b4:
        batch_cat = st.selectbox("Category", ["(none)"] + AVAILABLE_CATEGORIES, key="batch_cat")
    with col_b5:
        batch_n = st.number_input("How many per combination", min_value=1, max_value=20, value=1, key="batch_n")

    batch_total = batch_n * len(batch_tones) * len(batch_langs)
    st.metric("Total prompts to generate", batch_total)

    batch_model = st.selectbox(
        "Generator model",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index("claude_3_5_sonnet") if "claude_3_5_sonnet" in AVAILABLE_MODELS else 0,
        key="batch_gen_model",
    )
    st.caption("💡 Batch generation uses a single call per 10 prompts — a more capable model is recommended.")

    if st.button("✨ Generate batch"):
        if not batch_topic.strip():
            st.warning("Enter a topic first.")
        elif not batch_tones:
            st.warning("Select at least one tone.")
        elif not batch_langs:
            st.warning("Select at least one language.")
        else:
            client = get_client()
            combinations = [(t, l) for t in batch_tones for l in batch_langs] * batch_n

            n_calls = max(1, -(-len(combinations) // 10))  # ceil(total / 10)
            generated_batch = []
            try:
                with st.spinner(f"Generating {batch_total} prompts in {n_calls} call(s)…"):
                    generated_batch = generate_prompts_batch_via_llm(
                        client=client,
                        topic=batch_topic,
                        combinations=combinations,
                        model=batch_model,
                    )
            except Exception as exc:
                st.error(f"Batch generation failed: {exc}")
            if generated_batch:
                _batch_cat_val = batch_cat if batch_cat != "(none)" else None
                for item in generated_batch:
                    if _batch_cat_val:
                        item["category"] = _batch_cat_val
                st.session_state["generated_batch"] = generated_batch
                st.success(f"Generated {len(generated_batch)} prompts — review and save below.")

    if "generated_batch" in st.session_state:
        batch = st.session_state["generated_batch"]
        st.markdown(f"**{len(batch)} prompts ready to save:**")
        for i, p in enumerate(batch):
            cat_label = f" / {p['category']}" if p.get("category") else ""
            st.markdown(f"`[{p['tone']} / {p['language']}{cat_label}]` {p['prompt']}")
        col_save, col_discard = st.columns(2)
        with col_save:
            if st.button("💾 Save all to library", use_container_width=True):
                for p in batch:
                    prompts = add_prompt(prompts, p["prompt"], p["tone"], p["language"], p.get("category"))
                save_prompts(prompts)
                st.success(f"{len(batch)} prompts saved!")
                del st.session_state["generated_batch"]
                st.rerun()
        with col_discard:
            if st.button("🗑️ Discard", use_container_width=True):
                del st.session_state["generated_batch"]
                st.rerun()


# ---------------------------------------------------------------------------
# Tab: Results
# ---------------------------------------------------------------------------

with tab_results:
    st.header("Last Run Results")

    uploaded = st.file_uploader(
        "Load results from a previous session (.json)",
        type="json",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            loaded = json_to_results(uploaded.read().decode("utf-8"))
            st.session_state["last_results"] = loaded
            st.success(f"Loaded {len(loaded)} results from **{uploaded.name}**.")
        except Exception as exc:
            st.error(f"Could not parse file: {exc}")

    if "last_results" not in st.session_state:
        st.info("Run a test first or load a previously saved JSON file.")
    else:
        results: list[ModelResult] = st.session_state["last_results"]
        df = results_to_df(results, brand_groups)

        model_filter = st.multiselect(
            "Filter by model",
            options=df["Model"].unique().tolist(),
            default=df["Model"].unique().tolist(),
        )
        filtered_df = df[df["Model"].isin(model_filter)]

        st.dataframe(filtered_df, use_container_width=True)

        _download_buttons(
            [r for r in results if r.model in model_filter],
            filtered_df,
            key_suffix="results",
        )

        ok_df = filtered_df[filtered_df["OK"] == "✅"]

        st.subheader("Brand mentions by model")
        if not ok_df.empty:
            mentions = (
                ok_df.groupby(["Preferred Brand", "Model"])
                .size()
                .reset_index(name="Count")
            )
            st.altair_chart(_grouped_bar(mentions, "Preferred Brand", "Model"), use_container_width=True)
        else:
            st.info("No successful results to chart.")

        # --- Comparison by prompt category ---
        categories_present = sorted(ok_df["Category"].dropna().unique()) if not ok_df.empty else []
        categories_present = [c for c in categories_present if c]
        if categories_present:
            st.subheader("Brand preference by category")
            cat_filter = st.multiselect(
                "Select categories to compare",
                options=categories_present,
                default=categories_present,
                key="cat_filter_results",
            )
            cat_df = ok_df[ok_df["Category"].isin(cat_filter)]
            if not cat_df.empty:
                for cat in cat_filter:
                    sub = cat_df[cat_df["Category"] == cat]
                    if sub.empty:
                        continue
                    with st.expander(f"Category: **{cat}** ({len(sub)} results)", expanded=True):
                        summary = (
                            sub.groupby(["Preferred Brand", "Model"])
                            .size()
                            .reset_index(name="Count")
                        )
                        st.altair_chart(_grouped_bar(summary, "Preferred Brand", "Model"), use_container_width=True)
                        st.dataframe(
                            summary.sort_values(["Model", "Count"], ascending=[True, False]),
                            use_container_width=True, hide_index=True,
                        )

        # --- Comparison by tone ---
        tones_present = sorted(ok_df["Tone"].dropna().unique()) if not ok_df.empty else []
        tones_present = [t for t in tones_present if t]
        if tones_present:
            st.subheader("Brand preference by tone")
            tone_filter = st.multiselect(
                "Select tones to compare",
                options=tones_present,
                default=tones_present,
                key="tone_filter_results",
            )
            tone_df = ok_df[ok_df["Tone"].isin(tone_filter)]
            if not tone_df.empty:
                tone_summary = (
                    tone_df.groupby(["Tone", "Preferred Brand", "Model"])
                    .size()
                    .reset_index(name="Count")
                )
                st.altair_chart(
                    _grouped_bar(tone_summary, "Preferred Brand", "Model", facet="Tone"),
                    use_container_width=True,
                )
                st.dataframe(
                    tone_summary.sort_values(["Tone", "Model", "Count"], ascending=[True, True, False]),
                    use_container_width=True, hide_index=True,
                )

                # --- Radar chart: brand coverage per tone ---
                st.markdown("**Brand coverage by tone (radar)**")
                st.caption(
                    "For each tone (vertex), the share of prompts with that tone where the brand "
                    "was the preferred one — at a glance, which brands 'own' which tones."
                )
                import plotly.graph_objects as go

                _radar_brands = st.multiselect(
                    "Brands to plot",
                    options=sorted(tone_df["Preferred Brand"].dropna().unique()),
                    default=sorted(tone_df["Preferred Brand"].dropna().unique())[:5],
                    key="radar_brands",
                )
                if _radar_brands:
                    _tone_totals = tone_df.groupby("Tone").size()
                    _fig = go.Figure()
                    for _brand in _radar_brands:
                        _brand_df = tone_df[tone_df["Preferred Brand"] == _brand]
                        _per_tone = _brand_df.groupby("Tone").size()
                        _r = [
                            (_per_tone.get(_t, 0) / _tone_totals[_t] * 100) if _tone_totals[_t] else 0
                            for _t in tone_filter
                        ]
                        _fig.add_trace(go.Scatterpolar(
                            r=_r + [_r[0]],
                            theta=tone_filter + [tone_filter[0]],
                            fill="toself",
                            name=_brand,
                        ))
                    _fig.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")),
                        showlegend=True,
                        height=450,
                    )
                    st.plotly_chart(_fig, use_container_width=True)
                else:
                    st.info("Select at least one brand to plot.")

        st.subheader("Average confidence by model")
        if not ok_df.empty:
            conf_df = ok_df.groupby("Model")["Confidence"].mean().reset_index()
            conf_df.columns = ["Model", "Avg Confidence"]
            st.bar_chart(conf_df.set_index("Model"))

        web_results_all = [r for r in results if r.model in model_filter and r.web_search_used and r.search_results]
        if web_results_all:
            from urllib.parse import urlparse

            st.subheader("🔍 Web source analytics")

            all_sources = [src for r in web_results_all for src in r.search_results]
            domains = [urlparse(src["url"]).netloc.removeprefix("www.") for src in all_sources]
            domain_series = pd.Series(domains, name="Mentions")
            domain_counts = domain_series.value_counts().reset_index()
            domain_counts.columns = ["Domain", "Mentions"]

            col_tbl, col_chart = st.columns([1, 2])
            with col_tbl:
                st.dataframe(domain_counts, use_container_width=True, hide_index=True)
            with col_chart:
                st.bar_chart(domain_counts.set_index("Domain"))

            st.caption(f"{len(all_sources)} total sources across {len(web_results_all)} runs — {len(domain_counts)} unique domains")

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
        else:
            if r.error:
                st.error(f"**API error:** {r.error}")
            if r.json_parse_error:
                st.warning(f"**JSON parse error:** {r.json_parse_error}")
            if r.schema_error:
                st.warning(f"**Schema error:** {r.schema_error}")
            st.code(r.raw_response or "(empty response)", language="json")


# ---------------------------------------------------------------------------
# Tab: Brand Groups
# ---------------------------------------------------------------------------

with tab_brands:
    st.header("Brand Groups")
    st.markdown(
        "Define canonical brand names and their aliases. "
        "When results are displayed, any alias is automatically replaced by its canonical name."
    )

    # Reload so edits from this session are reflected
    brand_groups_edit = load_brand_groups()

    if brand_groups_edit:
        st.subheader("Current groups")
        for idx, group in enumerate(brand_groups_edit):
            col_a, col_b, col_c = st.columns([2, 4, 1])
            with col_a:
                st.markdown(f"**{group['canonical']}**")
            with col_b:
                st.caption(", ".join(group.get("aliases", [])) or "_(no aliases)_")
            with col_c:
                if st.button("🗑️", key=f"del_group_{idx}", help="Delete this group"):
                    brand_groups_edit.pop(idx)
                    save_brand_groups(brand_groups_edit)
                    st.rerun()
    else:
        st.info("No brand groups defined yet.")

    st.divider()
    st.subheader("Add a new group")
    col_cano, col_alias = st.columns([2, 4])
    with col_cano:
        new_canonical = st.text_input("Canonical name", placeholder="e.g. NexGard")
    with col_alias:
        new_aliases_raw = st.text_input(
            "Aliases (comma-separated)",
            placeholder="e.g. Nexgard, NEXGARD, nexgard spectra",
        )

    if st.button("➕ Add group", type="primary"):
        if not new_canonical.strip():
            st.warning("Enter a canonical name.")
        else:
            aliases = [a.strip() for a in new_aliases_raw.split(",") if a.strip()]
            # Avoid duplicates: check if canonical already exists
            existing_canonicals = [g["canonical"].lower() for g in brand_groups_edit]
            if new_canonical.strip().lower() in existing_canonicals:
                st.warning(f"A group for **{new_canonical.strip()}** already exists. Delete it first.")
            else:
                brand_groups_edit.append({"canonical": new_canonical.strip(), "aliases": aliases})
                save_brand_groups(brand_groups_edit)
                st.success(f"Group **{new_canonical.strip()}** saved with {len(aliases)} alias(es).")
                st.rerun()


# ---------------------------------------------------------------------------
# Tab: Content Analysis
# ---------------------------------------------------------------------------

with tab_content:
    st.header("Content Analysis")
    st.markdown(
        "Analyze the web snippets read by the AI before recommending each brand. "
        "Understand what content characteristics drive brand recommendations."
    )

    if "last_results" not in st.session_state:
        st.info("Run a test with web search enabled first, or load a JSON file in the Results tab.")
    else:
        _all_results: list[ModelResult] = st.session_state["last_results"]
        _web_ok = [r for r in _all_results if r.web_search_used and r.search_results and r.success]

        if not _web_ok:
            st.warning("No successful results with web search data found. Run tests with web search enabled.")
        else:
            from collections import defaultdict

            # Group snippets by preferred_brand
            _brand_snippets: dict[str, list[dict]] = defaultdict(list)
            for _r in _web_ok:
                for _src in _r.search_results:
                    _brand_snippets[_r.preferred_brand].append({
                        "snippet": _src["snippet"],
                        "url": _src["url"],
                        "title": _src["title"],
                        "prompt": _r.user_prompt,
                        "model": _r.model,
                        "ai_rationale": (_r.parsed_json or {}).get("confidence_rationale", ""),
                    })

            _brands_available = sorted(_brand_snippets.keys())

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Brands with web data", len(_brands_available))
            with col_s2:
                st.metric("Results with web search", len(_web_ok))
            with col_s3:
                st.metric("Total snippets", sum(len(v) for v in _brand_snippets.values()))

            _brands_to_compare = st.multiselect(
                "Select brands to compare",
                options=_brands_available,
                default=_brands_available[:min(3, len(_brands_available))],
                key="content_brands",
            )

            if not _brands_to_compare:
                st.warning("Select at least one brand.")
            else:
                # Per-brand snippet preview
                for _brand in _brands_to_compare:
                    _snippets = _brand_snippets[_brand]
                    _brand_lower = _brand.lower()
                    _n_mention = sum(1 for s in _snippets if _brand_lower in s["snippet"].lower())
                    _mention_pct = _n_mention / len(_snippets) * 100 if _snippets else 0

                    with st.expander(
                        f"**{_brand}** — {len(_snippets)} snippets | brand cited in {_mention_pct:.0f}% of snippets"
                    ):
                        if _mention_pct > 70:
                            st.success(
                                f"Brand name found in {_mention_pct:.0f}% of snippets "
                                "→ recommendation likely driven by web content"
                            )
                        elif _mention_pct > 30:
                            st.warning(
                                f"Brand name found in {_mention_pct:.0f}% of snippets "
                                "→ mixed signal: web content + prior knowledge"
                            )
                        else:
                            st.error(
                                f"Brand name found in only {_mention_pct:.0f}% of snippets "
                                "→ recommendation from prior knowledge, not web content"
                            )

                        for _i, _s in enumerate(_snippets[:8]):
                            st.markdown(f"**[{_s['title']}]({_s['url']})**")
                            st.caption(
                                f"Prompt: _{_s['prompt'][:80]}…_ | Model: `{_s['model']}`"
                            )
                            st.markdown(_s["snippet"])
                            if _i < min(7, len(_snippets) - 1):
                                st.divider()

                # LLM comparative analysis
                st.subheader("LLM Comparative Analysis")

                _analysis_model = st.selectbox(
                    "Analysis model",
                    options=AVAILABLE_MODELS,
                    index=AVAILABLE_MODELS.index("claude_4_6_sonnet") if "claude_4_6_sonnet" in AVAILABLE_MODELS else 0,
                    key="content_analysis_model",
                )
                _max_snippets = st.slider(
                    "Max snippets per brand",
                    min_value=5,
                    max_value=30,
                    value=15,
                    help="More snippets = richer analysis but higher token usage",
                )

                _include_rationale = st.toggle(
                    "Include AI rationale alongside snippets",
                    value=False,
                    help="Adds the model's confidence_rationale next to each snippet — shows what the AI extracted, not just what it read",
                )

                if st.button("🔍 Run analysis", type="primary", key="run_content_analysis"):
                    _sections = []
                    for _brand in _brands_to_compare:
                        _sample = _brand_snippets[_brand][:_max_snippets]
                        _parts = []
                        for _s in _sample:
                            _entry = f"[Source: {_s['title']}]\n{_s['snippet']}"
                            if _include_rationale and _s.get("ai_rationale"):
                                _entry += f"\n[AI rationale after reading: {_s['ai_rationale']}]"
                            _parts.append(_entry)
                        _joined = "\n---\n".join(_parts)
                        _sections.append(
                            f"### Brand: {_brand} ({len(_sample)} snippets)\n{_joined}"
                        )

                    _analysis_prompt = (
                        "You are analyzing web content snippets that an AI read before recommending "
                        "specific veterinary product brands. The snippets below are grouped by the brand "
                        "the AI ultimately recommended after reading them.\n\n"
                        + "\n\n".join(_sections)
                        + "\n\nAnalyze and compare across brands:\n"
                        "1. **Content characteristics**: What language, claims, or signals are typical for each brand's snippets?\n"
                        "2. **Authority signals**: Which brand's content uses more clinical references, studies, or expert endorsements?\n"
                        "3. **Recommendation clarity**: Which brand's snippets contain clearer, more direct recommendations that an AI can extract?\n"
                        "4. **AI-friendliness**: Which brand's content is better structured for AI consumption "
                        "(specific product names, direct claims, explicit conclusions)?\n"
                        "5. **Gaps**: What is missing in the underperforming brand's content that the leading brand has?\n\n"
                        "Be specific and cite examples from the snippets. "
                        "Structure: one section per brand, then a comparative summary with actionable suggestions."
                    )

                    with st.spinner("Analyzing…"):
                        try:
                            _resp = get_client().chat(
                                messages=[{"role": "user", "content": _analysis_prompt}],
                                model=_analysis_model,
                                temperature=0.3,
                                max_tokens=2000,
                            )
                            st.session_state["content_analysis"] = _resp.choices[0].message.content
                        except Exception as _exc:
                            st.error(f"Analysis failed: {_exc}")

                if "content_analysis" in st.session_state:
                    st.markdown(st.session_state["content_analysis"])
                    st.download_button(
                        "⬇️ Download analysis",
                        data=st.session_state["content_analysis"].encode("utf-8"),
                        file_name="content_analysis.md",
                        mime="text/markdown",
                        key="dl_content_analysis",
                    )

with tab_source_eval:
    st.header("Source Evaluation Summary")
    st.markdown(
        "Aggregates the compact `source_evaluation` digest that each model attaches to its "
        "response (source strength, tone, decisive factor) and synthesizes one overall "
        "evaluation per brand — without re-reading raw snippets, keeping token usage low."
    )

    if "last_results" not in st.session_state:
        st.info("Run a test first, or load a JSON file in the Results tab.")
    else:
        _se_results: list[ModelResult] = st.session_state["last_results"]
        _se_ok = [r for r in _se_results if r.success and r.source_evaluation]

        if not _se_ok:
            st.warning(
                "No successful results with a `source_evaluation` digest found. "
                "Run a new test — older results predate this field."
            )
        else:
            from collections import defaultdict

            # Group digests by normalized preferred_brand
            _brand_digests: dict[str, list[dict]] = defaultdict(list)
            for _r in _se_ok:
                _brand = normalize_brand(_r.preferred_brand, brand_groups)
                _se = _r.source_evaluation
                _brand_digests[_brand].append({
                    "source_strength": _se.get("source_strength", ""),
                    "source_strength_reason": _se.get("source_strength_reason", ""),
                    "tone_detected": _se.get("tone_detected", ""),
                    "tone_alignment": _se.get("tone_alignment", ""),
                    "decisive_factor": _se.get("decisive_factor", ""),
                    "model": _r.model,
                    "prompt": _r.user_prompt,
                })

            _se_brands_available = sorted(_brand_digests.keys())

            col_se1, col_se2 = st.columns(2)
            with col_se1:
                st.metric("Brands with digests", len(_se_brands_available))
            with col_se2:
                st.metric("Digests collected", len(_se_ok))

            _se_brands_to_compare = st.multiselect(
                "Select brands to evaluate",
                options=_se_brands_available,
                default=_se_brands_available[:min(3, len(_se_brands_available))],
                key="source_eval_brands",
            )

            if not _se_brands_to_compare:
                st.warning("Select at least one brand.")
            else:
                for _brand in _se_brands_to_compare:
                    _digests = _brand_digests[_brand]
                    _strength_counts = defaultdict(int)
                    _alignment_counts = defaultdict(int)
                    for _d in _digests:
                        _strength_counts[_d["source_strength"] or "unknown"] += 1
                        _alignment_counts[_d["tone_alignment"] or "unknown"] += 1

                    with st.expander(f"**{_brand}** — {len(_digests)} digests"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.caption("Source strength distribution")
                            st.write(dict(_strength_counts))
                        with c2:
                            st.caption("Tone alignment distribution")
                            st.write(dict(_alignment_counts))
                        for _d in _digests[:8]:
                            st.markdown(
                                f"- **{_d['source_strength'] or '?'}** "
                                f"(tone: {_d['tone_detected'] or '?'}, alignment: {_d['tone_alignment'] or '?'}) "
                                f"— {_d['source_strength_reason']}\n"
                                f"  - decisive factor: _{_d['decisive_factor']}_ "
                                f"(`{_d['model']}`)"
                            )

                st.subheader("LLM Brand Synthesis")

                _se_uploaded = st.file_uploader(
                    "Load a previously saved synthesis (.md)",
                    type="md",
                    key="source_eval_synthesis_uploader",
                )
                if _se_uploaded is not None:
                    st.session_state["source_eval_synthesis"] = _se_uploaded.read().decode("utf-8")
                    st.success(f"Loaded synthesis from **{_se_uploaded.name}**.")

                _se_analysis_model = st.selectbox(
                    "Synthesis model",
                    options=AVAILABLE_MODELS,
                    index=AVAILABLE_MODELS.index("claude_4_6_sonnet") if "claude_4_6_sonnet" in AVAILABLE_MODELS else 0,
                    key="source_eval_model",
                )

                if st.button("🧭 Run synthesis", type="primary", key="run_source_eval_synthesis"):
                    _se_sections = []
                    for _brand in _se_brands_to_compare:
                        _digests = _brand_digests[_brand]
                        _parts = [
                            f"- strength={_d['source_strength']}, tone={_d['tone_detected']}, "
                            f"alignment={_d['tone_alignment']}: {_d['source_strength_reason']} "
                            f"(decisive factor: {_d['decisive_factor']})"
                            for _d in _digests
                        ]
                        _se_sections.append(
                            f"### Brand: {_brand} ({len(_digests)} digests)\n" + "\n".join(_parts)
                        )

                    _se_prompt = (
                        "You are reviewing compact per-response evaluation digests collected while an AI "
                        "answered veterinary product questions and recommended specific brands. Each digest "
                        "is the AI's own brief self-assessment of the sources/knowledge it relied on for that "
                        "single recommendation (strength relative to the recommended brand, dominant tone, "
                        "tone alignment with the requested tone, and the single most decisive factor).\n\n"
                        + "\n\n".join(_se_sections)
                        + "\n\nFor each brand, summarize:\n"
                        "1. **Overall source strength**: Are the sources behind this brand's recommendations "
                        "generally strong, mixed, or weak — and why (cite recurring reasons)?\n"
                        "2. **Tone**: What tone dominates, and how well does it align with the tone the AI was "
                        "asked to use? Note any recurring misalignments.\n"
                        "3. **Decisive factors**: What recurring elements tip the decision toward this brand?\n\n"
                        "Then add a brief comparative conclusion: which brand's case is most solidly supported, "
                        "and which is weakest, and why. Be concise and base every claim only on the digests above."
                    )

                    with st.spinner("Synthesizing…"):
                        try:
                            _se_resp = get_client().chat(
                                messages=[{"role": "user", "content": _se_prompt}],
                                model=_se_analysis_model,
                                temperature=0.3,
                                max_tokens=2000,
                            )
                            st.session_state["source_eval_synthesis"] = _se_resp.choices[0].message.content
                        except Exception as _exc:
                            st.error(f"Synthesis failed: {_exc}")

                if "source_eval_synthesis" in st.session_state:
                    st.markdown(st.session_state["source_eval_synthesis"])
                    st.download_button(
                        "⬇️ Download synthesis",
                        data=st.session_state["source_eval_synthesis"].encode("utf-8"),
                        file_name="source_evaluation_synthesis.md",
                        mime="text/markdown",
                        key="dl_source_eval_synthesis",
                    )
