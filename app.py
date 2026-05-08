import streamlit as st
import io
import json
from backend import DataGenBot, get_editable_prompt


RESULT_STATE_KEYS = [
    "result_signature",
    "result_logs",
    "result_df",
    "result_json",
    "result_output_format",
    "result_element_type",
]


def clear_result_state():
    for key in RESULT_STATE_KEYS:
        st.session_state[key] = None


def render_saved_result():
    output_format = st.session_state.get("result_output_format")
    element_type = st.session_state.get("result_element_type")
    final_logs = st.session_state.get("result_logs") or []
    final_df = st.session_state.get("result_df")
    final_json = st.session_state.get("result_json")

    if output_format is None or element_type is None:
        return

    total_records = len(final_json) if output_format == "json" else len(final_df)
    st.success(f"✅ Successfully generated **{total_records} records** for `{element_type}`!")

    st.subheader("📋 Generation Logs")
    with st.expander("Logs", expanded=True):
        st.code("\n".join(final_logs), language="text")

    st.subheader("👀 Preview (first 50 records)")
    if output_format == "json":
        st.json(final_json[:50], expanded=False)
        st.markdown("**Output format:** `JSON`  |  **Top-level type:** `list[object]`")
    else:
        st.dataframe(final_df.head(50), use_container_width=True)
        st.markdown(f"**Total rows:** `{len(final_df)}`  |  **Columns:** `{list(final_df.columns)}`")

    st.subheader("⬇️ Download")
    if output_format == "json":
        json_bytes = json.dumps(final_json, indent=2).encode("utf-8")
        filename = f"synthetic_{element_type.lower()}_{len(final_json)}_records.json"
        st.download_button(
            label="📥 Download JSON",
            data=json_bytes,
            file_name=filename,
            mime="application/json",
            use_container_width=True,
            type="primary"
        )
    else:
        csv_buffer = io.StringIO()
        final_df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        filename = f"synthetic_{element_type.lower()}_{len(final_df)}_rows.csv"
        st.download_button(
            label="📥 Download CSV",
            data=csv_bytes,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Synthetic Data Generator",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 Synthetic Data Generator")
st.caption("Powered by Databricks LLM · Generates synthetic CSV and JSON data in batches")

for key in RESULT_STATE_KEYS:
    st.session_state.setdefault(key, None)

# ── Sidebar — Configuration ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    data_type = st.selectbox(
        "Element Type",
        options=["Cluster", "ProductVendor"],
        help="Select the element type to generate"
    )

    num_rows = st.number_input(
        "Total Rows to Generate",
        min_value=10,
        max_value=10000,
        value=1000,
        step=50,
        help="Total number of synthetic rows you want"
    )

    batch_size = st.number_input(
        "Batch Size (rows per LLM call)",
        min_value=10,
        max_value=200,
        value=100,
        step=10,
        help="Rows requested per API call. 100 is optimal — higher risks truncation."
    )

    # API settings are hardcoded — not exposed in UI
    api_key = "dapi7ea4cfa21cac326cdb0320c9d72af0e0-2"
    base_url = "https://adb-4224005571705028.8.azuredatabricks.net/serving-endpoints"
    model_name = "databricks-claude-sonnet-4-5"

    st.divider()
    st.caption(f"📦 Est. API calls: **{max(1, -(-int(num_rows) // int(batch_size)))}**")

# ── Main area ────────────────────────────────────────────────────────────────

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📝 Prompt")

    display_prompt = get_editable_prompt(data_type)
    st.info(f"Selected Element Type: **{data_type}**", icon="🧩")

    st.info(
        "✏️ **Tweak the prompt below** to customize data generation rules. "
        "Leave it as-is to use the default. The row count per batch is injected automatically from your settings.",
        icon="💡"
    )

    custom_prompt = st.text_area(
        "Prompt (editable)",
        value=display_prompt,
        height=320,
        help="Modify rules here. Do NOT add row count — it is controlled by the Total Rows setting."
    )

    # Detect if user actually changed the prompt from default
    is_custom = custom_prompt.strip() != display_prompt.strip()
    if is_custom:
        st.success("✅ Custom prompt will be used.")
    else:
        st.info("ℹ️ Default prompt will be used (no changes detected).")

with col2:
    st.subheader("▶️ Run Generation")

    st.markdown(f"""
    | Setting | Value |
    |---|---|
    | Element Type | `{data_type}` |
    | Total Rows | `{num_rows}` |
    | Batch Size | `{batch_size}` rows/call |
    | Est. API Calls | `{max(1, -(-int(num_rows) // int(batch_size)))}` |
    """)

    run_btn = st.button("🚀 Generate Data", type="primary", use_container_width=True)

st.divider()

current_signature = {
    "element_type": data_type,
    "num_rows": int(num_rows),
    "batch_size": int(batch_size),
}

saved_signature = st.session_state.get("result_signature")
if saved_signature is not None and saved_signature != current_signature:
    clear_result_state()

# ── Generation Logic ─────────────────────────────────────────────────────────
if run_btn:
    status_box = st.empty()
    progress_bar = st.progress(0, text="Starting...")
    final_logs = []
    final_df = None
    final_json = None
    output_format = None

    try:
        with status_box.container():
            st.info("⏳ Generating data, please wait...")

        bot = DataGenBot(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            data_type=data_type,
            num_rows=int(num_rows),
            batch_size=int(batch_size),
            custom_prompt=custom_prompt if is_custom else ""
        )

        for status in bot.generate_stream():
            batch_num = status["batch_num"]
            num_batches = status["num_batches"]
            logs = status["logs"]
            output_format = status["output_format"]

            # ── Update progress bar ──────────────────────────────────────────
            pct = int((batch_num / num_batches) * 100)
            progress_bar.progress(pct, text=f"API call {batch_num}/{num_batches} complete ({pct}%)")

            if status["done"]:
                final_logs = logs
                final_df = status["final_df"]
                final_json = status["final_json"]

        if output_format == "json" and final_json is None:
            raise RuntimeError("Generation completed without final JSON output.")
        if output_format != "json" and final_df is None:
            raise RuntimeError("Generation completed without a final dataframe.")

        # ── Final state ──────────────────────────────────────────────────────
        progress_bar.progress(100, text="✅ Done!")
        status_box.empty()
        st.session_state["result_signature"] = current_signature
        st.session_state["result_logs"] = final_logs
        st.session_state["result_df"] = final_df
        st.session_state["result_json"] = final_json
        st.session_state["result_output_format"] = output_format
        st.session_state["result_element_type"] = data_type

    except Exception as e:
        progress_bar.empty()
        status_box.empty()
        st.error(f"❌ Generation failed: {e}")
        st.exception(e)


render_saved_result()


