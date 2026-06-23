import streamlit as st
import io
import json
import math
import time
import pandas as pd
from backend import (
    DataGenBot, estimate_token_count, get_editable_prompt, MAX_BATCH_SIZES,
    MAX_OUTPUT_TOKENS, MODEL_NAME,
    build_realistic_prompt,
)
from profiler import (
    profile_databricks_table, list_tables, get_row_count,
    DATABRICKS_HOST, DATABRICKS_CATALOG, DATABRICKS_SCHEMA,
)


# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Synthetic Data Generator",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #e8f4fd; }
[data-testid="stMain"] { background: #e8f4fd; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #c5dff8; border-right: 1px solid #90bfee; }
[data-testid="stSidebar"] * { color: #1a3a5c !important; }

/* ── General text ── */
body, p, span, div, label { color: #1a3a5c; }

/* ── Title ── */
h1 { background: linear-gradient(90deg, #1565c0, #0288d1);
     -webkit-background-clip: text; -webkit-text-fill-color: transparent;
     font-size: 2.4rem !important; font-weight: 800 !important; }

/* ── Headings ── */
h2, h3, h4 { color: #1565c0 !important; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #ffffff; border: 1px solid #90bfee; border-radius: 10px;
    padding: 12px 16px !important;
}
[data-testid="stMetricValue"] { font-size: 1.6rem !important; color: #1565c0 !important; }
[data-testid="stMetricLabel"] { color: #4a6fa5 !important; font-size: .78rem !important; }

/* ── Buttons ── */
button[kind="primary"] {
    background: linear-gradient(135deg, #1565c0, #0288d1) !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; letter-spacing: .04em !important;
    color: #ffffff !important; transition: opacity .2s !important;
}
button[kind="primary"]:hover { opacity: .85 !important; }

/* ── Code blocks / logs ── */
.stCode pre { font-size: 0.75rem !important; max-height: 280px; overflow-y: auto;
              background: #f0f7ff !important; color: #1a3a5c !important; }

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div { background: linear-gradient(90deg, #1565c0, #0288d1) !important; }

/* ── Tabs ── */
button[data-baseweb="tab"] { font-weight: 600 !important; color: #1a3a5c !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #1565c0 !important;
    border-bottom-color: #1565c0 !important; }

/* ── Expanders ── */
[data-testid="stExpander"] { background: #f0f7ff; border: 1px solid #90bfee; border-radius: 8px; }

/* ── Text area / inputs ── */
textarea, input[type="number"] { background: #ffffff !important; color: #1a3a5c !important;
    border: 1px solid #90bfee !important; }
</style>
""", unsafe_allow_html=True)


# ── Session-state keys ────────────────────────────────────────────────────────
RESULT_STATE_KEYS = [
    "result_signature", "result_logs", "result_df",
    "result_json", "result_output_format", "result_element_type",
    "result_total_elapsed",
]

REALISTIC_RESULT_STATE_KEYS = [
    "realistic_result_logs", "realistic_result_df",
    "realistic_result_json", "realistic_result_output_format",
    "realistic_result_element_type", "realistic_result_total_elapsed",
]

# ── Token-budget constants shown in the realistic prompt UI ──────────────────
# Context window:  200,000 tokens  (Claude Sonnet total input+output budget)
# Output cap:        8,192 tokens  (max tokens the model writes per call)
# Max safe prompt  = 200,000 − 8,192 = ~191,808 tokens
#
# Soft warning at 150,000 — well below the hard ceiling; normal profiling
# prompts are 500–5,000 tokens so this only fires if the prompt is bloated.
REALISTIC_PROMPT_WARNING_TOKENS = 150_000  # soft UI warning (prompt tokens)
REALISTIC_MODEL_CONTEXT_TOKENS  = 200_000  # Claude Sonnet full context window
_REALISTIC_MAX_SAFE_PROMPT      = REALISTIC_MODEL_CONTEXT_TOKENS - 8_192   # 191,808

def clear_result_state():
    for key in RESULT_STATE_KEYS:
        st.session_state[key] = None

def _fmt_time(seconds: float) -> str:
    """Format seconds as mm:ss or Xs."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"

# ── Results renderer (shared by both tabs, driven by key prefix) ───────────────
def render_saved_result(prefix: str = "result"):
    """
    prefix="result"    → custom generation tab keys
    prefix="realistic" → realistic data tab keys
    """
    def _k(short):
        return short if prefix == "result" else f"{prefix}_{short}"

    output_format = st.session_state.get(_k("result_output_format"))
    element_type  = st.session_state.get(_k("result_element_type"))
    final_logs    = st.session_state.get(_k("result_logs")) or []
    final_df      = st.session_state.get(_k("result_df"))
    final_json    = st.session_state.get(_k("result_json"))
    total_elapsed = st.session_state.get(_k("result_total_elapsed")) or 0

    if output_format is None or element_type is None:
        st.markdown("""
        <div style='text-align:center; padding: 60px 0; color: #4a6fa5;'>
            <div style='font-size:3rem;'>🧬</div>
            <div style='font-size:1.1rem; margin-top:8px; color: #1a3a5c;'>
                Configure your settings and click <b>🚀 Generate Data</b> to begin.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    total_records = len(final_json) if output_format == "json" else len(final_df)
    rps = total_records / total_elapsed if total_elapsed > 0 else 0

    st.success(f"✅ Generated **{total_records:,} records** for `{element_type}` in {_fmt_time(total_elapsed)}")

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("📦 Records", f"{total_records:,}")
    mc2.metric("⚡ Records / sec", f"{rps:.1f}")
    mc3.metric("🕒 Total Time", _fmt_time(total_elapsed))
    mc4.metric("📂 Format", output_format.upper())

    st.divider()

    tab_preview, tab_logs, tab_download = st.tabs(["👀 Preview", "📋 Logs", "⬇️ Download"])

    with tab_preview:
        st.caption("Showing first 50 records")
        if output_format == "json":
            st.json(final_json[:50], expanded=False)
            st.markdown(f"**Type:** `list[object]`  |  **Total:** `{len(final_json):,}` objects")
        else:
            st.dataframe(final_df.head(50), use_container_width=True)
            st.markdown(
                f"**Total rows:** `{len(final_df):,}`  |  "
                f"**Columns:** `{list(final_df.columns)}`"
            )

    with tab_logs:
        st.code("\n".join(final_logs), language="text")

    with tab_download:
        st.markdown("### Download your data")
        dl_col1, dl_col2 = st.columns(2)
        if output_format == "json":
            json_bytes = json.dumps(final_json, indent=2).encode("utf-8")
            filename = f"synthetic_{element_type.lower()}_{len(final_json)}_records.json"
            with dl_col1:
                st.download_button(
                    label="📥 Download JSON", data=json_bytes, file_name=filename,
                    mime="application/json", use_container_width=True, type="primary",
                )
        else:
            csv_buf = io.StringIO()
            final_df.to_csv(csv_buf, index=False)
            csv_bytes = csv_buf.getvalue().encode("utf-8")
            filename_csv = f"synthetic_{element_type.lower()}_{len(final_df)}_rows.csv"
            with dl_col1:
                st.download_button(
                    label="📥 Download CSV", data=csv_bytes, file_name=filename_csv,
                    mime="text/csv", use_container_width=True, type="primary",
                )
            xlsx_buf = io.BytesIO()
            with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                final_df.to_excel(writer, index=False, sheet_name="SyntheticData")
            xlsx_bytes = xlsx_buf.getvalue()
            filename_xlsx = f"synthetic_{element_type.lower()}_{len(final_df)}_rows.xlsx"
            with dl_col2:
                st.download_button(
                    label="📊 Download Excel", data=xlsx_bytes, file_name=filename_xlsx,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )


# ── Shared generation runner ───────────────────────────────────────────────────
def run_generation(bot: DataGenBot, result_prefix: str, element_label: str):
    """
    Drive bot.generate_stream(), show live UI, persist results under result_prefix.
    result_prefix="result"    → custom generation keys
    result_prefix="realistic" → realistic generation keys
    """
    status_box   = st.empty()
    progress_bar = st.progress(0, text="🚀 Starting generation...")
    metrics_ph   = st.empty()
    preview_ph   = st.empty()
    logs_ph      = st.empty()

    final_logs    = []
    final_df      = None
    final_json    = None
    output_format = None
    t_start       = time.time()

    try:
        with status_box.container():
            st.info("⏳ Sending batches to the model — live updates below…")

        for status in bot.generate_stream():
            batch_done    = status["batch_num"]
            num_batches   = status["num_batches"]
            output_format = status["output_format"]
            elapsed       = time.time() - t_start

            pct = int((batch_done / num_batches) * 100)
            progress_bar.progress(pct, text=f"Batches completed: {batch_done}/{num_batches}  ({pct}%)")

            records_so_far = (
                len(status["partial_json"]) if status["partial_json"] is not None
                else (len(status["partial_df"]) if status["partial_df"] is not None else 0)
            )
            rps_live     = records_so_far / elapsed if elapsed > 0 else 0
            batches_left = num_batches - batch_done
            eta          = (batches_left / batch_done * elapsed) if batch_done > 0 else 0

            with metrics_ph.container():
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("✅ Batches Done",   f"{batch_done}/{num_batches}")
                m2.metric("📦 Records So Far", f"{records_so_far:,}")
                m3.metric("⚡ Rec/s",          f"{rps_live:.1f}")
                m4.metric("⏳ ETA",            _fmt_time(eta) if not status["done"] else "—")

            if not status["done"] and records_so_far > 0:
                with preview_ph.container():
                    with st.expander("🔍 Live Preview (latest data)", expanded=False):
                        if status["partial_json"]:
                            st.json(status["partial_json"][:5], expanded=False)
                        elif status["partial_df"] is not None:
                            st.dataframe(status["partial_df"].head(10), use_container_width=True)

            with logs_ph.container():
                with st.expander("📋 Live Logs", expanded=False):
                    st.code("\n".join(status["logs"]), language="text")

            if status["done"]:
                final_logs = status["logs"]
                final_df   = status["final_df"]
                final_json = status["final_json"]

        if output_format == "json" and final_json is None:
            raise RuntimeError("Generation completed without final JSON output.")
        if output_format != "json" and final_df is None:
            raise RuntimeError("Generation completed without a final dataframe.")

        total_elapsed = time.time() - t_start
        progress_bar.progress(100, text=f"✅ Done!  Took {_fmt_time(total_elapsed)}")
        status_box.empty()
        preview_ph.empty()
        logs_ph.empty()

        def _k(short):
            return short if result_prefix == "result" else f"{result_prefix}_{short}"

        st.session_state[_k("result_logs")]           = final_logs
        st.session_state[_k("result_df")]             = final_df
        st.session_state[_k("result_json")]           = final_json
        st.session_state[_k("result_output_format")]  = output_format
        st.session_state[_k("result_element_type")]   = element_label
        st.session_state[_k("result_total_elapsed")]  = total_elapsed

    except Exception as e:
        progress_bar.empty()
        status_box.empty()
        st.error(f"❌ Generation failed: {e}")
        st.exception(e)


# ── Page header ───────────────────────────────────────────────────────────────
st.title("🧬 Synthetic Data Generator")
st.caption("Powered by Databricks · Claude Sonnet 4.6 · Generates synthetic CSV and JSON data in parallel batches")

for key in RESULT_STATE_KEYS:
    st.session_state.setdefault(key, None)
for key in REALISTIC_RESULT_STATE_KEYS:
    st.session_state.setdefault(key, None)
st.session_state.setdefault("realistic_profile", None)
st.session_state.setdefault("realistic_tables", None)
st.session_state.setdefault("realistic_table_row_count", None)  # preview before full profile

# ── Sidebar — Configuration (Custom Generation tab) ───────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    st.markdown("""
    <div style='background:#1565c0;color:#fff;border-radius:6px;padding:6px 10px;
         font-size:0.8rem;font-weight:600;margin-bottom:8px;'>
        🤖 Applies to: Custom Generation tab only
    </div>
    """, unsafe_allow_html=True)
    st.caption(
        "Switching to the **🔬 Realistic (Real Data Table)** tab? "
        "Those settings are configured inline inside that tab — "
        "nothing here will affect it."
    )

    data_type = st.selectbox(
        "Element Type",
        options=["Cluster", "ProductVendor"],
        help="Select the element type to generate",
    )

    st.divider()

    num_rows = st.number_input(
        "Total Rows to Generate",
        min_value=10, max_value=10000, value=1000, step=50,
        help="Total number of synthetic rows you want",
    )

    batch_size = st.number_input(
        "Batch Size (rows per LLM call)",
        min_value=10, max_value=200, value=100, step=10,
        help=(
            "Rows requested per API call. "
            "The model has an 8 192 output-token budget per call. "
            "Cluster CSV rows use ~15 tokens each (safe up to ~150/batch). "
            "ProductVendor JSON objects use ~80 tokens each (safe up to ~50/batch). "
            "The app auto-caps to the safe limit for the selected type."
        ),
    )

    _safe_limit   = MAX_BATCH_SIZES.get(data_type, 100)
    _effective_bs = min(int(batch_size), _safe_limit)
    if int(batch_size) > _safe_limit:
        st.warning(
            f"⚠️ **Batch size capped to {_safe_limit}** for `{data_type}`.  \n"
            f"Exceeding {_safe_limit} rows/call risks output truncation.",
            icon="🔒",
        )

    st.divider()

    with st.expander("🔧 Advanced Settings", expanded=False):
        parallelism = st.slider(
            "Parallel API Calls", min_value=1, max_value=5, value=3,
            help=(
                "Number of batches sent concurrently. "
                "Higher = faster overall, but increases load on the endpoint. "
                "Reduce to 1 if you hit rate-limit errors."
            ),
        )
        temperature = st.slider(
            "Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.05,
            help=(
                "Controls randomness. Lower = more deterministic (fewer duplicates); "
                "higher = more varied output."
            ),
        )

    _num_batches_est = max(1, -(-int(num_rows) // _effective_bs))
    _parallel_rounds = max(1, math.ceil(_num_batches_est / parallelism))
    st.divider()
    st.caption(f"📦 Batches: **{_num_batches_est}**  ·  🔀 Parallel rounds ≈ **{_parallel_rounds}**")


# ── Two top-level tabs ────────────────────────────────────────────────────────
main_tab_custom, main_tab_realistic = st.tabs(
    ["🤖 Custom Generation", "🔬 Realistic (Real Data Table)"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Custom Generation (original behaviour, unchanged)
# ══════════════════════════════════════════════════════════════════════════════
with main_tab_custom:
    col_prompt, col_run = st.columns([3, 2], gap="large")

    with col_prompt:
        st.subheader("📝 Prompt")
        st.info(f"Selected Element Type: **{data_type}**", icon="🧩")
        st.info(
            "✏️ **Tweak the prompt below** to customise generation rules. "
            "The row count per batch is injected automatically.",
            icon="💡",
        )

        display_prompt = get_editable_prompt(data_type)
        custom_prompt  = st.text_area(
            "Prompt (editable)",
            value=display_prompt,
            height=300,
            help="Modify rules here. Do NOT add row count — it is controlled by the Total Rows setting.",
        )
        is_custom = custom_prompt.strip() != display_prompt.strip()
        if is_custom:
            st.success("✅ Custom prompt active.")
        else:
            st.info("ℹ️ Using default prompt.")

    with col_run:
        st.subheader("▶️ Run Generation")

        st.markdown(f"""
| Setting | Value |
|---|---|
| Element Type | `{data_type}` |
| Total Rows | `{int(num_rows):,}` |
| Requested Batch | `{int(batch_size)}` rows/call |
| **Effective Batch** | **`{_effective_bs}`** ({'⚠️ capped' if int(batch_size) > _safe_limit else '✅ as-entered'}) |
| Est. Batches | `{_num_batches_est}` |
| Parallel Calls | `{parallelism}` |
| Temperature | `{temperature}` |
""")

        run_btn = st.button("🚀 Generate Data", type="primary", use_container_width=True)

    st.divider()

    # ── Signature-based result invalidation ───────────────────────────────────
    current_signature = {
        "element_type": data_type,
        "num_rows":     int(num_rows),
        "batch_size":   int(batch_size),
    }
    saved_signature = st.session_state.get("result_signature")
    if saved_signature is not None and saved_signature != current_signature:
        clear_result_state()

    # ── Generation ────────────────────────────────────────────────────────────
    if run_btn:
        bot = DataGenBot(
            model_name=MODEL_NAME,
            api_key="",
            base_url="",
            data_type=data_type,
            num_rows=int(num_rows),
            batch_size=int(batch_size),
            custom_prompt=custom_prompt if is_custom else "",
            parallelism=parallelism,
            temperature=temperature,
        )
        run_generation(bot, "result", data_type)
        st.session_state["result_signature"] = current_signature
        st.rerun()

    render_saved_result("result")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Realistic Data Generation from Real Data Table
# ══════════════════════════════════════════════════════════════════════════════
with main_tab_realistic:
    # ── Sidebar-scope notice ──────────────────────────────────────────────────
    st.info(
        "ℹ️ **Sidebar settings do not apply here.** "
        "Element type, batch size, and parallel calls for this tab are configured "
        "inline in **Step 4** below.",
        icon="👈",
    )

    st.subheader("🔬 Realistic Data Generation from Real Data Table")
    st.markdown(
        "Profile a Databricks table to extract its real data patterns, "
        "then generate realistic synthetic rows that mirror the actual data distribution."
    )

    # ── Step 1: Table selection ───────────────────────────────────────────────
    st.markdown("### Step 1 — Select Table")

    # Show hardcoded connection context so the user knows what workspace is being used
    st.info(
        f"🔐 **Workspace:** `{DATABRICKS_HOST}`  ·  "
        f"**Catalog:** `{DATABRICKS_CATALOG}`  ·  "
        f"**Schema:** `{DATABRICKS_SCHEMA}`",
        icon="🏢",
    )

    # ── Load / refresh table list ─────────────────────────────────────────────
    load_tables_btn = st.button(
        "🔄 Load Tables",
        help=f"Fetch managed tables in {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}",
    )
    if load_tables_btn:
        with st.spinner(f"⏳ Fetching managed tables from `{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}`…"):
            try:
                _fetched = list_tables()
                st.session_state["realistic_tables"] = _fetched
                st.session_state["realistic_profile"] = None
                for k in REALISTIC_RESULT_STATE_KEYS:
                    st.session_state[k] = None
                st.success(f"✅ Found **{len(_fetched)}** managed tables.")
            except Exception as e:
                st.error(f"❌ Could not load tables: {e}")
                st.exception(e)

    _available_tables = st.session_state.get("realistic_tables")

    if not _available_tables:
        st.caption("Click **🔄 Load Tables** above to populate the table list.")
        r_selected_table = None
    else:
        r_selected_table = st.selectbox(
            f"Select a managed table from `{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}`",
            options=_available_tables,
            index=0,
            key="realistic_selected_table",
            help="Only managed tables are listed (external tables and views are excluded).",
        )

        # Clear cached row count whenever the selection changes
        if st.session_state.get("_last_selected_table") != r_selected_table:
            st.session_state["realistic_table_row_count"] = None
            st.session_state["_last_selected_table"] = r_selected_table

    _r_table_fqn = (
        f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.{r_selected_table}"
        if r_selected_table else ""
    )

    # ── Row-count preview — see actual size before choosing sample ────────────
    if r_selected_table:
        _preview_row_count = st.session_state.get("realistic_table_row_count")

        rc_col, hint_col = st.columns([1, 3])
        with rc_col:
            check_rc_btn = st.button(
                "📊 Check Row Count",
                help="Quick COUNT(*) so you can choose an appropriate sample size",
            )
        with hint_col:
            if _preview_row_count is not None:
                # ── Dynamic recommendation based on actual row count ───────────
                if _preview_row_count <= 20_000:
                    _rec_sample = _preview_row_count
                    _rec_msg = (
                        f"Table is small — use **all {_preview_row_count:,} rows** as the sample "
                        f"(fully accurate, still fast)."
                    )
                elif _preview_row_count <= 100_000:
                    _rec_sample = 10_000
                    _pct = round(_rec_sample / _preview_row_count * 100)
                    _rec_msg = (
                        f"Recommended sample: **{_rec_sample:,} rows** "
                        f"(~{_pct}% of {_preview_row_count:,}) — accurate and fast."
                    )
                elif _preview_row_count <= 500_000:
                    _rec_sample = 20_000
                    _pct = round(_rec_sample / _preview_row_count * 100, 1)
                    _rec_msg = (
                        f"Recommended sample: **{_rec_sample:,} rows** "
                        f"(~{_pct}% of {_preview_row_count:,}) — good coverage."
                    )
                else:
                    _rec_sample = 50_000
                    _pct = round(_rec_sample / _preview_row_count * 100, 1)
                    _rec_msg = (
                        f"Large table — recommended sample: **{_rec_sample:,} rows** "
                        f"(~{_pct}% of {_preview_row_count:,})."
                    )
                st.info(
                    f"**`{r_selected_table}`** has **{_preview_row_count:,} rows**. {_rec_msg}",
                    icon="📊",
                )
            else:
                st.caption("Click **📊 Check Row Count** to see the table size before choosing a sample size.")

        if check_rc_btn:
            with st.spinner(f"Counting rows in `{_r_table_fqn}`…"):
                try:
                    _rc = get_row_count(table_fqn=_r_table_fqn)
                    st.session_state["realistic_table_row_count"] = _rc
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Row count failed: {e}")

    # ── Profile sample size — set AFTER seeing row count, BEFORE profiling ────
    r_sample_rows = st.number_input(
        "📐 Profile Sample Size (rows)",
        min_value=1_000, max_value=100_000, value=10_000, step=1_000,
        help=(
            "How many rows to randomly sample for statistics. "
            "Click 📊 Check Row Count first to see the actual table size, "
            "then set this to 10–20% of total rows (min 10 000 for accuracy). "
            "Does NOT affect how many synthetic rows are generated."
        ),
        key="realistic_sample_rows",
    )


    # ── Profile the selected table ────────────────────────────────────────────
    profile_btn = st.button(
        "🔍 Profile Table",
        type="primary",
        disabled=(not r_selected_table),
        help="Reads column statistics from the selected table using the sample size above",
    )

    if profile_btn and _r_table_fqn:
        with st.spinner(f"⏳ Profiling `{_r_table_fqn}` — sampling {r_sample_rows:,} rows…"):
            try:
                _new_profile = profile_databricks_table(
                    table_fqn=_r_table_fqn,
                    sample_rows=int(r_sample_rows),
                    top_values=int(st.session_state.get("realistic_top_values", 200)),
                )
                st.session_state["realistic_profile"] = _new_profile
                # Update the preview row count from the profile result (free)
                st.session_state["realistic_table_row_count"] = _new_profile["row_count"]
                for k in REALISTIC_RESULT_STATE_KEYS:
                    st.session_state[k] = None
                st.success(
                    f"✅ Profiled **{len(_new_profile['columns'])} columns** "
                    f"across **{_new_profile['row_count']:,} actual rows** in `{_new_profile['table']}` "
                    f"(statistics computed from a {_new_profile.get('sample_rows', '?'):,}-row sample)"
                )
            except Exception as e:
                st.error(f"❌ Profiling failed: {e}")
                st.exception(e)

    # ── Show rest of UI only after a successful profile ───────────────────────
    _profile = st.session_state.get("realistic_profile")

    if _profile:
        # ── Step 2: Profile summary ───────────────────────────────────────────
        st.markdown("### Step 2 — Profile Summary")
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        p_col1.metric("📋 Table",                _profile["table"].split(".")[-1])
        p_col2.metric("📊 Columns",              len(_profile["columns"]))
        p_col3.metric("🗂️ Actual Table Rows",    f"{_profile['row_count']:,}")
        p_col4.metric("🔬 Rows Used for Stats",  f"{_profile.get('sample_rows', '—'):,}")

        st.caption(
            f"ℹ️ The **{_profile.get('sample_rows', 10_000):,} rows** figure is the random sample "
            f"used to compute column statistics — not the size of the table. "
            f"Your table has **{_profile['row_count']:,} actual rows**. "
            f"Synthetic data is generated **from scratch** by the LLM using those patterns; "
            f"no production rows are copied."
        )

        with st.expander("🔎 Per-Column Details", expanded=False):
            _kind_icon = {"numeric": "🔢", "string": "🔤", "date": "📅",
                          "boolean": "☑️", "other": "📌"}
            for _col in _profile["columns"]:
                _kind = _col.get("kind", "other")
                _icon = _kind_icon.get(_kind, "📌")
                with st.expander(
                    f"{_icon} **{_col['name']}** — `{_col['dtype']}` ({_kind})",
                    expanded=False,
                ):
                    dc1, dc2, dc3 = st.columns(3)
                    dc1.metric("Nullable", "Yes" if _col["nullable"] else "No")
                    dc2.metric("Null %",   f"{_col['null_pct']}%")

                    if _kind == "numeric":
                        dc3.metric("Range", f"{_col['min']} → {_col['max']}")
                        st.caption(f"Average: **{_col.get('mean')}**")
                    elif _kind == "date":
                        dc3.metric("Date Range", "see below")
                        st.caption(f"From **{_col['min_date']}** to **{_col['max_date']}**")
                    elif _kind == "boolean":
                        dc3.metric("True %", f"{_col['true_pct']}%")
                    elif _kind == "string":
                        _dc = _col.get("distinct_count", 0)
                        dc3.metric("Distinct Values (approx)", f"{_dc:,}")
                        _tv = _col.get("top_values", [])
                        if _tv:
                            _show_n = min(50, len(_tv))
                            st.caption(
                                "**Top values (% in sample):** " +
                                ", ".join(
                                    f"`{e['value']}` ({e['freq_pct']}%)"
                                    if e.get("freq_pct") is not None
                                    else f"`{e['value']}`"
                                    for e in _tv[:_show_n]
                                ) +
                                (f"  …+{len(_tv) - _show_n} more" if len(_tv) > _show_n else "")
                            )

        # ── Step 2b: Adjust distinct-value cap based on what you saw above ─────
        st.divider()

        # Build a quick summary of string columns + how many values were fetched
        _str_cols = [
            c for c in _profile["columns"] if c.get("kind") == "string"
        ]
        if _str_cols:
            _str_summary_parts = []
            _any_real_gap = False
            for _sc in _str_cols:
                _dc      = _sc.get("distinct_count", 0)
                _fetched = len(_sc.get("top_values", []))
                # APPROX_COUNT_DISTINCT has inherent imprecision (~2–5%).
                # Treat any gap within max(5 values, 5% of estimate) as fully covered
                # so users don't chase false ⚠️ warnings from the approximation.
                _tolerance = max(5, round(_dc * 0.05))
                if _fetched >= _dc:
                    _coverage = "✅ all fetched"
                elif _fetched >= _dc - _tolerance:
                    _coverage = (
                        f"✅ ~all fetched ({_fetched} in sample; "
                        f"APPROX_COUNT_DISTINCT ≈ {_dc:,} — within approximation margin)"
                    )
                else:
                    _coverage = f"⚠️ {_fetched} / ~{_dc:,} fetched — increase limit & re-profile"
                    _any_real_gap = True
                _str_summary_parts.append(
                    f"**{_sc['name']}**: ~{_dc:,} distinct  ({_coverage})"
                )
            _footer = (
                "\n\nIf any column shows ⚠️, increase the limit below and click **🔄 Re-profile**."
                if _any_real_gap
                else "\n\n✅ All string columns are fully covered in the prompt."
            )
            st.info(
                "📊 **String column distinct-value coverage** (based on current profile):\n\n" +
                "  \n".join(_str_summary_parts) +
                _footer,
                icon="🔤",
            )

        # ── Pre-compute token budget for Step-2b hints (before the widget) ────
        _tv_prompt_now   = build_realistic_prompt(_profile, batch_size=50)
        _tv_tokens_now   = estimate_token_count(_tv_prompt_now)
        _tv_headroom     = REALISTIC_PROMPT_WARNING_TOKENS - _tv_tokens_now
        _tv_ctx_headroom = REALISTIC_MODEL_CONTEXT_TOKENS  - _tv_tokens_now - 8_192  # keep output budget
        _tv_n_str_cols   = max(1, len([c for c in _profile["columns"] if c.get("kind") == "string"]))
        # Each additional distinct value costs ≈7 tokens in the prompt
        # ("value" (X.X%), ) × all string columns that are currently capped.
        _tv_tokens_per_extra_val = 7 * _tv_n_str_cols
        _tv_safe_increase = (
            max(0, int(_tv_headroom / _tv_tokens_per_extra_val))
            if _tv_tokens_per_extra_val > 0 else 0
        )

        tv_col, reprof_col = st.columns([2, 1], gap="medium")
        with tv_col:
            r_top_values = st.number_input(
                "🔤 Max Distinct Values per String Column",
                min_value=10, max_value=5000,
                value=int(st.session_state.get("realistic_top_values", 200)),
                step=10,
                help=(
                    "How many distinct values to fetch from the DB for each string/categorical column. "
                    "When a column has FEWER distinct values than this limit, ALL of them are fetched "
                    "automatically — so if a column has 76 values and this is set to 200, all 76 appear "
                    "in the prompt. "
                    "Increase freely while the Token Budget panel stays green. "
                    "Each extra value adds ~5–10 tokens to the prompt per string column."
                ),
                key="realistic_top_values",
            )
        with reprof_col:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            reprof_btn = st.button(
                "🔄 Re-profile with updated limit",
                use_container_width=True,
                help="Re-runs profiling using the new Max Distinct Values limit above",
                key="realistic_reprof_btn",
            )

        # ── Token-budget feedback: tells the user when to stop increasing ────────
        if _tv_tokens_now >= _REALISTIC_MAX_SAFE_PROMPT:
            st.error(
                f"⛔ **Prompt is {_tv_tokens_now:,} tokens — above the hard safe ceiling "
                f"({_REALISTIC_MAX_SAFE_PROMPT:,}).** Do NOT increase the distinct-value limit further. "
                f"Reduce the limit or shorten the rules in Step 3 before re-profiling.",
                icon="🚫",
            )
        elif _tv_tokens_now >= REALISTIC_PROMPT_WARNING_TOKENS:
            st.warning(
                f"⚠️ **Prompt is already {_tv_tokens_now:,} tokens** — at or above the soft warning "
                f"({REALISTIC_PROMPT_WARNING_TOKENS:,}). Increasing the distinct-value limit may push "
                f"you over the context window. Re-profile only if you have reduced the limit or "
                f"trimmed rules in Step 3.",
                icon="⚠️",
            )
        elif _tv_tokens_now >= REALISTIC_PROMPT_WARNING_TOKENS * 0.75:
            st.warning(
                f"🟡 **Getting close:** prompt is **{_tv_tokens_now:,} tokens** "
                f"({int(_tv_tokens_now / REALISTIC_PROMPT_WARNING_TOKENS * 100)}% of soft limit). "
                f"~{_tv_headroom:,} tokens of headroom left — roughly "
                f"**+{_tv_safe_increase:,} more distinct values** across {_tv_n_str_cols} string "
                f"column(s) before the warning triggers.",
                icon="🟡",
            )
        else:
            st.info(
                f"✅ **Token headroom: ~{_tv_headroom:,} tokens** "
                f"({100 - int(_tv_tokens_now / REALISTIC_PROMPT_WARNING_TOKENS * 100)}% free before "
                f"soft warning). You can safely add roughly "
                f"**+{_tv_safe_increase:,} more distinct values** "
                f"across {_tv_n_str_cols} string column(s). "
                f"Increase the limit above, then click **🔄 Re-profile** — "
                f"watch the Token Budget panel in Step 3 after each re-profile.",
                icon="💡",
            )

        if reprof_btn and _r_table_fqn:
            with st.spinner(
                f"⏳ Re-profiling `{_r_table_fqn}` with top_values={r_top_values}…"
            ):
                try:
                    _reprof = profile_databricks_table(
                        table_fqn=_r_table_fqn,
                        sample_rows=int(r_sample_rows),
                        top_values=int(r_top_values),
                    )
                    st.session_state["realistic_profile"] = _reprof
                    st.session_state["realistic_table_row_count"] = _reprof["row_count"]
                    for k in REALISTIC_RESULT_STATE_KEYS:
                        st.session_state[k] = None
                    # Explicitly rebuild the prompt from the NEW profile and store
                    # it in session state so the Step-3 text area picks it up on
                    # rerun.  Simply popping the key is not enough — Streamlit can
                    # restore the old widget value from its internal render cache.
                    _new_preview  = build_realistic_prompt(_reprof, batch_size=50)
                    _new_editable = "\n".join(_new_preview.splitlines()[2:]).strip()
                    st.session_state["realistic_prompt_editor"] = _new_editable
                    st.success(
                        f"✅ Re-profiled with **top_values={r_top_values}**. "
                        f"String columns now carry up to {r_top_values} distinct values in the prompt."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Re-profile failed: {e}")
                    st.exception(e)

        st.divider()

        # ── Step 3: Prompt review ──────────────────────────────────────────────
        st.markdown("### Step 3 — Review / Edit Generated Prompt")
        st.info(
            "This prompt was auto-built from the real data table profile. "
            "Edit any rule before generating, e.g. to tighten value ranges or add business constraints.",
            icon="💡",
        )

        # Build a display version with placeholder batch size; user edits the rules body
        _full_prompt_preview = build_realistic_prompt(_profile, batch_size=50)
        _prompt_lines        = _full_prompt_preview.splitlines()
        # Remove the first two lines ("Generate exactly N rows…" + blank) so the
        # editor shows only the rules — the header is re-injected at runtime.
        _editable_default    = "\n".join(_prompt_lines[2:]).strip()

        r_custom_rules = st.text_area(
            "Rules (editable — batch-size header injected automatically)",
            value=_editable_default,
            height=340,
            key="realistic_prompt_editor",
        )

        # ── Token Budget Panel — shown immediately below the prompt editor ────
        # Use the persisted batch-size from session state so the estimate is
        # accurate even before the user scrolls down to Step 4.
        _tk_bs = int(st.session_state.get("realistic_batch_size", 50))
        _tk_rules = r_custom_rules.strip()
        _tk_changed = bool(_tk_rules) and _tk_rules != _editable_default.strip()
        _tk_prompt = (
            build_realistic_prompt(_profile, batch_size=_tk_bs)
            if not _tk_changed
            else f"Generate exactly {_tk_bs} UNIQUE CSV rows.\n\n{_tk_rules}"
        )
        _tk_tokens     = estimate_token_count(_tk_prompt)
        _tk_warn_left  = REALISTIC_PROMPT_WARNING_TOKENS - _tk_tokens
        _tk_ctx_left   = REALISTIC_MODEL_CONTEXT_TOKENS  - _tk_tokens
        _tk_pct        = min(int(_tk_tokens / REALISTIC_PROMPT_WARNING_TOKENS * 100), 100)

        # ── progress bar colour: green → amber → red ──────────────────────────
        if _tk_tokens < REALISTIC_PROMPT_WARNING_TOKENS * 0.6:
            _bar_color = "#22c55e"
        elif _tk_tokens < REALISTIC_PROMPT_WARNING_TOKENS:
            _bar_color = "#f59e0b"
        else:
            _bar_color = "#ef4444"

        st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #dbeafe, #eff6ff);
    border: 1.5px solid #3b82f6;
    border-radius: 12px;
    padding: 14px 18px 10px 18px;
    margin: 6px 0 14px 0;
">
  <div style="font-size:0.82rem; color:#1e40af; font-weight:700;
              letter-spacing:.03em; margin-bottom:10px;">
      🧮 TOKEN BUDGET
  </div>
  <div style="display:flex; flex-wrap:wrap; gap:24px; font-size:0.85rem; color:#1e3a8a;">
    <span>📝 <b>Prompt (est.):</b> {_tk_tokens:,} tokens</span>
    <span>⚠️ <b>Soft warning at:</b> {REALISTIC_PROMPT_WARNING_TOKENS:,}</span>
    <span>🪟 <b>Context window:</b> {REALISTIC_MODEL_CONTEXT_TOKENS:,}</span>
    <span>📤 <b>Output cap / call:</b> {MAX_OUTPUT_TOKENS:,}</span>
    <span>✅ <b>Context remaining:</b> {_tk_ctx_left:,}</span>
  </div>
  <div style="margin-top:10px;">
    <div style="font-size:0.75rem; color:#2563eb; margin-bottom:3px;">
        Prompt vs soft-warning threshold &nbsp;({_tk_pct}%)
    </div>
    <div style="background:#bfdbfe; border-radius:6px; height:10px; width:100%;">
      <div style="background:{_bar_color}; width:{_tk_pct}%; height:10px;
                  border-radius:6px; transition:width .3s;"></div>
    </div>
    <div style="font-size:0.73rem; color:#1d4ed8; margin-top:3px;">
        {_tk_warn_left:,} tokens remaining before soft warning
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        if _tk_tokens >= REALISTIC_PROMPT_WARNING_TOKENS:
            st.warning(
                f"⚠️ Prompt is **{_tk_tokens:,} tokens** ({_tk_pct}% of soft limit). "
                f"Consider shortening rules or lowering batch size."
            )

        # ── Step 4: Generation settings ────────────────────────────────────────
        st.markdown("### Step 4 — Generation Settings")
        rs1, rs2, rs3, rs4 = st.columns(4)
        with rs1:
            r_num_rows = st.number_input(
                "Total Rows", min_value=10, max_value=10000, value=500, step=50,
                key="realistic_num_rows",
            )
        with rs2:
            r_batch_size = st.number_input(
                "Batch Size", min_value=10, max_value=150, value=50, step=10,
                help="Reduce if the table has many wide columns.",
                key="realistic_batch_size",
            )
        with rs3:
            r_parallelism = st.slider(
                "Parallel Calls", min_value=1, max_value=5, value=3,
                key="realistic_parallelism",
            )
        with rs4:
            r_temperature = st.slider(
                "Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.05,
                key="realistic_temperature",
            )

        # ── Runtime variables (used for run logic and batch summary) ──────────
        _r_rules_text     = r_custom_rules.strip()
        _r_rules_changed  = bool(_r_rules_text) and _r_rules_text != _editable_default.strip()
        _r_current_batch_size = int(r_batch_size)
        _r_eff_bs    = min(_r_current_batch_size, MAX_BATCH_SIZES.get("RealisticTable", 100))
        _r_batches   = max(1, -(-int(r_num_rows) // _r_eff_bs))
        _r_rounds    = max(1, math.ceil(_r_batches / r_parallelism))
        st.caption(
            f"📦 Est. batches: **{_r_batches}**  ·  "
            f"🔀 Parallel rounds ≈ **{_r_rounds}**  ·  "
            f"📋 Columns in output: **{len(_profile['columns'])}**"
        )

        # ── Step 5: Generate ───────────────────────────────────────────────────
        st.markdown("### Step 5 — Generate")
        r_run_btn = st.button(
            "🚀 Generate Realistic Data",
            type="primary",
            use_container_width=True,
            key="realistic_run_btn",
        )

        if r_run_btn:
            _col_names     = [c["name"] for c in _profile["columns"]]

            _bot = DataGenBot(
                model_name=MODEL_NAME,
                api_key="",
                base_url="",
                data_type="RealisticTable",
                num_rows=int(r_num_rows),
                batch_size=_r_eff_bs,
                parallelism=r_parallelism,
                temperature=r_temperature,
                column_names=_col_names,
                profile=_profile,           # drives build_prompt per-batch
            )

            # If the user edited the rules, override with custom_prompt
            # (build_prompt will prepend the "Generate exactly N rows" header)
            if _r_rules_changed:
                _bot._profile      = None
                _bot.custom_prompt = _r_rules_text

            _table_label = _r_table_fqn.split(".")[-1]
            run_generation(_bot, "realistic", _table_label)
            st.rerun()

        st.divider()
        render_saved_result("realistic")

    else:
        # No profile yet — empty-state placeholder
        st.markdown("""
        <div style='text-align:center; padding: 60px 0; color: #4a6fa5;'>
            <div style='font-size:3rem;'>🔬</div>
            <div style='font-size:1.1rem; margin-top:8px; color: #1a3a5c;'>
                Click <b>🔄 Load Tables</b> to fetch tables from the schema,<br>
                pick a table from the dropdown, then click <b>🔍 Profile Table</b>.
            </div>
        </div>""", unsafe_allow_html=True)
