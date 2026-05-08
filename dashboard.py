"""
Client-facing presentation dashboard for the Synthetic Data Generation Agent.
Run with:  venv\Scripts\python.exe -m streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import json
import time
import random

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Synthetic Data Generation Agent — Capabilities",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Import Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Gradient hero */
.hero-banner {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 70%, #533483 100%);
    border-radius: 20px;
    padding: 50px 40px;
    text-align: center;
    margin-bottom: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
.hero-banner h1 {
    color: #ffffff;
    font-size: 2.8rem;
    font-weight: 800;
    margin: 0 0 10px 0;
    letter-spacing: -0.5px;
}
.hero-banner p {
    color: #a8b2d8;
    font-size: 1.2rem;
    margin: 0;
}
.hero-badge {
    display: inline-block;
    background: rgba(99,179,237,0.2);
    border: 1px solid rgba(99,179,237,0.5);
    color: #63b3ed;
    border-radius: 20px;
    padding: 4px 16px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 16px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1e3a5f, #0d2137);
    border: 1px solid rgba(99,179,237,0.3);
    border-radius: 16px;
    padding: 24px 20px;
    text-align: center;
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-4px); }
.metric-card .metric-value {
    color: #63b3ed;
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 6px;
}
.metric-card .metric-label {
    color: #a8b2d8;
    font-size: 0.9rem;
    font-weight: 500;
}

/* Section titles */
.section-title {
    font-size: 1.7rem;
    font-weight: 700;
    color: #e2e8f0;
    margin: 0 0 6px 0;
}
.section-sub {
    color: #718096;
    font-size: 1rem;
    margin-bottom: 24px;
}

/* Feature card */
.feature-card {
    background: #1a202c;
    border: 1px solid #2d3748;
    border-radius: 14px;
    padding: 24px;
    height: 100%;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.feature-card:hover {
    border-color: #4299e1;
    box-shadow: 0 0 20px rgba(66,153,225,0.15);
}
.feature-icon { font-size: 2rem; margin-bottom: 10px; }
.feature-title { font-weight: 700; color: #e2e8f0; font-size: 1.05rem; margin-bottom: 6px; }
.feature-desc { color: #718096; font-size: 0.9rem; line-height: 1.5; }

/* Architecture steps */
.arch-step {
    background: #1a202c;
    border-left: 4px solid #4299e1;
    border-radius: 0 12px 12px 0;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.arch-step-num { color: #4299e1; font-weight: 700; font-size: 0.8rem; text-transform: uppercase; }
.arch-step-title { color: #e2e8f0; font-weight: 600; font-size: 1rem; margin: 2px 0; }
.arch-step-desc { color: #718096; font-size: 0.88rem; }

/* Use-case pill */
.use-case-pill {
    display: inline-block;
    background: linear-gradient(135deg, #2d3748, #1a202c);
    border: 1px solid #4a5568;
    border-radius: 24px;
    padding: 8px 20px;
    margin: 4px;
    color: #e2e8f0;
    font-size: 0.9rem;
    font-weight: 500;
}

/* Schema card */
.schema-card {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    font-family: monospace;
}

/* CTA */
.cta-banner {
    background: linear-gradient(135deg, #0f3460, #533483);
    border-radius: 16px;
    padding: 40px;
    text-align: center;
    margin-top: 30px;
}
.cta-banner h2 { color: #fff; font-weight: 800; margin-bottom: 8px; }
.cta-banner p { color: #a8b2d8; margin-bottom: 20px; }

/* Divider */
.custom-divider {
    height: 2px;
    background: linear-gradient(90deg, transparent, #4299e1, transparent);
    margin: 40px 0;
    border: none;
}

/* Nav tabs override */
div[data-testid="stHorizontalBlock"] > div { gap: 0 !important; }
</style>
""", unsafe_allow_html=True)


# ───────────────────────────── HERO ──────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
    <div class="hero-badge">🤖 AI-Powered · LLM-Driven · Enterprise Ready</div>
    <h1>Synthetic Data Generation Agent</h1>
    <p>Generate realistic, schema-compliant synthetic datasets at scale using large language models — <br>
    fully configurable, batch-ready, and instantly downloadable.</p>
</div>
""", unsafe_allow_html=True)


# ──────────────────────── ANIMATED METRICS ──────────────────────────────────
st.markdown('<p class="section-title">📊 At a Glance</p>', unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
metrics = [
    (m1, "10,000+", "Records per Run"),
    (m2, "2", "Data Schema Types"),
    (m3, "< 2s", "Avg. Batch Latency"),
    (m4, "2×", "Auto-Retry on Failure"),
    (m5, "CSV + JSON", "Output Formats"),
]
for col, val, label in metrics:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{val}</div>
            <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ──────────────────────── CAPABILITIES ───────────────────────────────────────
st.markdown('<p class="section-title">⚡ Core Capabilities</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Everything you need to generate, validate, and export high-quality synthetic data.</p>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
features = [
    (c1, "🧠", "LLM-Powered Generation",
     "Leverages Databricks-hosted Claude (Anthropic) to generate contextually rich, realistic data following business rules."),
    (c2, "📋", "Schema Enforcement",
     "Every record is validated against strict field rules — correct formats, uniqueness, nested structures, and data types."),
    (c3, "🔄", "Batch Streaming",
     "Large datasets are split into configurable batches. Progress is streamed live with per-batch retry on failure."),
    (c4, "⚙️", "Prompt Customisation",
     "Business users can edit generation prompts directly in the UI — no code changes needed to adjust data rules."),
]
for col, icon, title, desc in features:
    with col:
        st.markdown(f"""
        <div class="feature-card">
            <div class="feature-icon">{icon}</div>
            <div class="feature-title">{title}</div>
            <div class="feature-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)
c5, c6, c7, c8 = st.columns(4)
features2 = [
    (c5, "📥", "Multi-Format Download",
     "Download results as CSV (tabular data) or JSON (nested/hierarchical) with a single click."),
    (c6, "🔁", "Fault-Tolerant Retries",
     "Each batch automatically retries up to 2 times on parse or API errors, ensuring maximum data yield."),
    (c7, "🔍", "Live Preview",
     "Instantly preview the first 50 generated records in the UI before downloading the full dataset."),
    (c8, "📈", "Scalable Volume",
     "From 10 to 10,000+ records per run, with configurable batch sizes to avoid LLM context limits."),
]
for col, icon, title, desc in features2:
    with col:
        st.markdown(f"""
        <div class="feature-card">
            <div class="feature-icon">{icon}</div>
            <div class="feature-title">{title}</div>
            <div class="feature-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ─────────────────────── DATA TYPES SHOWCASE ─────────────────────────────────
st.markdown('<p class="section-title">🗂️ Supported Data Schemas</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Two production-grade schemas are available out of the box, with more easily added.</p>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["  📦 Cluster (CSV)  ", "  🛍️ ProductVendor (JSON)  "])

with tab1:
    col_left, col_right = st.columns([1, 1], gap="large")
    with col_left:
        st.markdown("#### Schema Definition")
        st.markdown("""
        | Column | Type | Rules |
        |---|---|---|
        | `STORE_NO` | String | 4-digit zero-padded, digits 1–9 |
        | `DEPT_NO` | String | `G5-` + 2–4 alphanumeric chars |
        | `CSTD_GRADE` | String | Exactly 2 alphanumeric chars |
        | `PHASE_STARTDATE` | String | `DD-MMM-YY` format |
        """)
        st.markdown("**Output:** Raw CSV rows · No header in LLM output · Header injected by parser")
        st.markdown("**Use cases:** Store planning, inventory clustering, retail ops simulation")
    with col_right:
        st.markdown("#### Sample Output")
        sample_cluster = pd.DataFrame({
            "STORE_NO": ["0142", "0587", "0931", "0274", "0816"],
            "DEPT_NO":  ["G5-AB12", "G5-XY3", "G5-MN45", "G5-QR2", "G5-LK89"],
            "CSTD_GRADE": ["A1", "B3", "C2", "A4", "B1"],
            "PHASE_STARTDATE": ["15-Jan-25", "22-Mar-25", "07-Jun-25", "30-Sep-25", "11-Nov-25"],
        })
        st.dataframe(sample_cluster, use_container_width=True, hide_index=True)
        st.success("✅ Unique STORE_NO and DEPT_NO enforced per batch")

with tab2:
    col_left, col_right = st.columns([1, 1], gap="large")
    with col_left:
        st.markdown("#### Schema Definition")
        st.markdown("""
        | Field | Type | Rules |
        |---|---|---|
        | `productId` | String | 18-digit, zero-padded |
        | `season.seasonYear` | String | 4-digit year |
        | `season.seasonName` | String | Unique code (e.g. `SP24`) |
        | `vendors[].supplierNumber` | String | 6-char, starts with `M` |
        | `vendors[].factoryNumber` | String | 11-digit string |
        | `vendors[].isActive` | String | `"true"` or `"false"` |
        """)
        st.markdown("**Output:** Nested JSON array · Multi-vendor per product · Validated on parse")
        st.markdown("**Use cases:** Product catalogue simulation, vendor management, supply chain testing")
    with col_right:
        st.markdown("#### Sample Output")
        sample_json = [
            {
                "productId": "000000000006059884",
                "season": {"seasonYear": "2025", "seasonName": "SP25"},
                "vendors": [
                    {"supplierNumber": "M00055", "factoryNumber": "10000142751", "isActive": "true"}
                ]
            },
            {
                "productId": "000000000009182736",
                "season": {"seasonYear": "2024", "seasonName": "FA24"},
                "vendors": [
                    {"supplierNumber": "M00122", "factoryNumber": "10000387514", "isActive": "false"},
                    {"supplierNumber": "M00389", "factoryNumber": "10000594823", "isActive": "true"}
                ]
            }
        ]
        st.json(sample_json, expanded=True)

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ───────────────────────── ARCHITECTURE ──────────────────────────────────────
st.markdown('<p class="section-title">🏗️ How It Works</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">A clean, modular pipeline from user config to downloadable data.</p>', unsafe_allow_html=True)

arch_col, diagram_col = st.columns([1, 1], gap="large")

with arch_col:
    steps = [
        ("01", "Configure", "Select data type, total rows, and batch size in the sidebar. Optionally edit the generation prompt."),
        ("02", "Build Prompt", "The agent auto-injects the batch size instruction. Your custom rules are merged into the LLM prompt."),
        ("03", "LLM API Call", "Each batch is sent to Databricks Claude via the OpenAI-compatible endpoint. Temperature=0.7 for variety."),
        ("04", "Parse & Validate", "CSV rows are parsed with Pandas; JSON objects are validated against the schema — field by field."),
        ("05", "Retry on Error", "Any failed batch is retried up to 2 times automatically before being skipped and logged."),
        ("06", "Stream Results", "Progress is streamed live to the UI. The final dataset is stored in session state for preview & download."),
    ]
    for num, title, desc in steps:
        st.markdown(f"""
        <div class="arch-step">
            <div class="arch-step-num">Step {num}</div>
            <div class="arch-step-title">{title}</div>
            <div class="arch-step-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

with diagram_col:
    st.markdown("#### System Architecture")
    st.code("""
┌─────────────────────────────────────────┐
│              Streamlit UI               │
│  • Data type selector                   │
│  • Row count & batch size config        │
│  • Editable prompt editor               │
│  • Live progress bar                    │
│  • Preview table / JSON viewer          │
│  • CSV / JSON download buttons          │
└──────────────────┬──────────────────────┘
                   │  calls
┌──────────────────▼──────────────────────┐
│             DataGenBot                  │
│  • build_prompt()                       │
│  • call_llm()  → Databricks API         │
│  • parse_csv_text() / parse_json()      │
│  • generate_stream()  (yields batches)  │
└──────────────────┬──────────────────────┘
                   │  OpenAI-compatible
┌──────────────────▼──────────────────────┐
│    Databricks Serving Endpoint          │
│    Model: Claude Sonnet (Anthropic)     │
│    Auth:  PAT token (DAPI)              │
└─────────────────────────────────────────┘
    """, language="text")

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ───────────────────────── USE CASES ─────────────────────────────────────────
st.markdown('<p class="section-title">💼 Use Cases</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Synthetic data unlocks a wide range of enterprise scenarios without exposing real data.</p>', unsafe_allow_html=True)

use_cases = [
    "🧪 QA & Testing Without PII", "🏗️ Development Environment Seeding",
    "📊 BI & Analytics Prototyping", "🤖 ML Model Training Data",
    "🔐 Privacy-Safe Data Sharing", "🌐 API Integration Testing",
    "📦 Inventory & Supply Chain Simulation", "🛍️ Retail Planning Models",
    "🔄 ETL Pipeline Validation", "📐 Schema & Contract Testing",
    "🎓 Training & Demo Environments", "💡 Proof-of-Concept Acceleration",
]
pills_html = "".join(f'<span class="use-case-pill">{uc}</span>' for uc in use_cases)
st.markdown(f'<div style="line-height:2.5">{pills_html}</div>', unsafe_allow_html=True)

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ──────────────────────── INTERACTIVE DEMO ───────────────────────────────────
st.markdown('<p class="section-title">🎮 Live Demo Simulation</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">See the agent in action — click Generate to simulate a batch run.</p>', unsafe_allow_html=True)

demo_col1, demo_col2 = st.columns([1, 2], gap="large")

with demo_col1:
    demo_type = st.selectbox("Data Schema", ["Cluster (CSV)", "ProductVendor (JSON)"])
    demo_rows = st.slider("Records to simulate", 5, 50, 10, step=5)
    demo_btn = st.button("⚡ Simulate Generation", type="primary", use_container_width=True)

with demo_col2:
    if demo_btn:
        with st.spinner("🤖 Agent is generating synthetic data..."):
            time.sleep(1.2)  # Simulate latency

        if "CSV" in demo_type:
            grades = ["A1","B2","C3","A2","B1","C1","A3","D1"]
            months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            rows = []
            stores = random.sample(range(1111, 9999), demo_rows)
            depts = [f"G5-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=random.randint(2,4)))}" for _ in range(demo_rows)]
            for i in range(demo_rows):
                rows.append({
                    "STORE_NO": f"{stores[i]:04d}",
                    "DEPT_NO": depts[i],
                    "CSTD_GRADE": random.choice(grades),
                    "PHASE_STARTDATE": f"{random.randint(1,28):02d}-{random.choice(months)}-{random.randint(24,26):02d}",
                })
            df = pd.DataFrame(rows)
            st.success(f"✅ Generated {demo_rows} Cluster records")
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv_bytes = df.to_csv(index=False).encode()
            st.download_button("📥 Download Sample CSV", data=csv_bytes,
                               file_name=f"demo_cluster_{demo_rows}.csv", mime="text/csv")
        else:
            seasons = [("2024","SP24"),("2024","FA24"),("2025","SP25"),("2025","FA25"),("2026","SP26")]
            objects = []
            for i in range(demo_rows):
                sy, sn = random.choice(seasons)
                num_vendors = random.randint(1, 3)
                vendors = []
                for _ in range(num_vendors):
                    vendors.append({
                        "supplierNumber": f"M{random.randint(10000,99999):05d}",
                        "factoryNumber": str(random.randint(10000000000, 99999999999)),
                        "isActive": random.choice(["true","false"]),
                    })
                objects.append({
                    "productId": str(random.randint(10**17, 10**18 - 1)).zfill(18),
                    "season": {"seasonYear": sy, "seasonName": sn},
                    "vendors": vendors,
                })
            st.success(f"✅ Generated {demo_rows} ProductVendor records")
            st.json(objects[:5], expanded=False)
            if demo_rows > 5:
                st.caption(f"...and {demo_rows - 5} more records")

            json_bytes = json.dumps(objects, indent=2).encode()
            st.download_button("📥 Download Sample JSON", data=json_bytes,
                               file_name=f"demo_productvendor_{demo_rows}.json", mime="application/json")
    else:
        st.info("👆 Configure options on the left and click **Simulate Generation** to see the agent in action.")

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ──────────────────────── TECH STACK ─────────────────────────────────────────
st.markdown('<p class="section-title">🛠️ Technology Stack</p>', unsafe_allow_html=True)

t1, t2, t3, t4, t5 = st.columns(5)
tech = [
    (t1, "🐍", "Python 3.12", "Core runtime"),
    (t2, "🎈", "Streamlit", "Interactive UI"),
    (t3, "🤖", "Claude Sonnet", "LLM (Anthropic)"),
    (t4, "⚡", "Databricks", "Serving endpoint"),
    (t5, "🐼", "Pandas", "Data processing"),
]
for col, icon, name, desc in tech:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:2rem">{icon}</div>
            <div class="metric-value" style="font-size:1rem;color:#e2e8f0;margin-top:8px">{name}</div>
            <div class="metric-label">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ──────────────────────── EXTENSIBILITY ──────────────────────────────────────
st.markdown('<p class="section-title">🔌 Extensibility — Adding New Data Types</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">New schemas can be wired in minutes by following the 3-step pattern.</p>', unsafe_allow_html=True)

ext1, ext2, ext3 = st.columns(3)
ext_steps = [
    (ext1, "1️⃣", "Add Prompt Template",
     "`backend.py`",
     'PROMPT_TEMPLATES["MyType"] = """\nGenerate exactly {batch_size} ...\n"""'),
    (ext2, "2️⃣", "Register Columns & Format",
     "`backend.py`",
     'COLUMN_NAMES["MyType"] = ["COL_A", "COL_B"]\nOUTPUT_FORMATS["MyType"] = "csv"'),
    (ext3, "3️⃣", "Add to UI Selector",
     "`app.py`",
     'options=["Cluster", "ProductVendor", "MyType"]'),
]
for col, num, title, file, code in ext_steps:
    with col:
        st.markdown(f"#### {num} {title}")
        st.caption(f"File: `{file}`")
        st.code(code, language="python")

st.markdown('<hr class="custom-divider" />', unsafe_allow_html=True)


# ──────────────────────── CTA ────────────────────────────────────────────────
st.markdown("""
<div class="cta-banner">
    <h2>🚀 Ready to Generate Your Data?</h2>
    <p>Launch the full application and start generating schema-compliant synthetic datasets in seconds.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)
cta1, cta2, cta3 = st.columns(3)
with cta1:
    st.info("**Launch App**\n\n`venv\\Scripts\\python.exe -m streamlit run app.py`", icon="🚀")
with cta2:
    st.info("**Install Dependencies**\n\n`venv\\Scripts\\python.exe -m pip install -r requirements.txt`", icon="📦")
with cta3:
    st.info("**Download PPT**\n\n`venv\\Scripts\\python.exe create_ppt.py`", icon="📊")

# Footer
st.markdown("<br/><br/>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:#4a5568;font-size:0.85rem'>"
    "Synthetic Data Generation Agent · Powered by Databricks + Claude Sonnet · Built with Streamlit"
    "</p>",
    unsafe_allow_html=True,
)

