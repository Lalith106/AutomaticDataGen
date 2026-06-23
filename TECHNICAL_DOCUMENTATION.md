# Synthetic Data Generator — Complete Technical Documentation

> **Version:** June 2026  
> **Model:** `databricks-claude-sonnet-4-6`  
> **Platform:** Databricks (Azure) · Streamlit UI  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [File Reference](#3-file-reference)
4. [Core Components — Deep Dive](#4-core-components--deep-dive)
   - 4.1 [app.py — Streamlit UI](#41-apppy--streamlit-ui)
   - 4.2 [backend.py — Generation Engine](#42-backendpy--generation-engine)
   - 4.3 [profiler.py — Table Profiler](#43-profilerpy--table-profiler)
5. [Data Types & Output Formats](#5-data-types--output-formats)
6. [Generation Pipeline — Step by Step](#6-generation-pipeline--step-by-step)
7. [Realistic Table Generation Flow](#7-realistic-table-generation-flow)
8. [Token Budget System](#8-token-budget-system)
9. [Distinct Value Coverage System](#9-distinct-value-coverage-system)
10. [Batch & Retry Logic](#10-batch--retry-logic)
11. [Configuration Reference](#11-configuration-reference)
12. [Databricks Integration](#12-databricks-integration)
13. [How to Run](#13-how-to-run)
14. [How to Add a New Data Type](#14-how-to-add-a-new-data-type)
15. [Demo Q&A — Common Questions](#15-demo-qa--common-questions)

---

## 1. Project Overview

The **Synthetic Data Generator** is a Streamlit web application that uses a Large Language Model (LLM) — Claude Sonnet 4.6 hosted on Databricks — to generate synthetic tabular data. It supports two modes:

| Mode | Description | Output |
|------|-------------|--------|
| **Custom Generation** | User selects a pre-built data type (`Cluster`, `ProductVendor`) and optionally edits the prompt rules | CSV or JSON |
| **Realistic Table Generation** | User selects a real Databricks table, profiles its statistics, and generates data that mirrors the real distribution | CSV |

**Key capabilities:**
- Parallel batch generation (up to 5 concurrent LLM calls)
- Automatic retry per batch (up to 3 attempts)
- Top-up loop to fill any row shortfall
- Live progress bar, metrics, and log viewer
- Download as CSV, Excel, or JSON
- Token budget monitoring with colour-coded warnings
- Distinct value coverage panel with smart tolerance for APPROX_COUNT_DISTINCT inaccuracy

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      app.py (UI Layer)                  │
│                                                         │
│  Sidebar Config ──► Prompt Editor ──► Run Button        │
│        │                                   │            │
│        ▼                                   ▼            │
│  Tab 1: Custom Generation       Tab 2: Realistic Table  │
│  (Cluster / ProductVendor)      (any Databricks table)  │
│        │                                   │            │
│        └──────────────┬────────────────────┘            │
│                       ▼                                 │
│              DataGenBot.generate_stream()               │
│          (yields status dicts → live UI update)         │
└───────────────────────┬─────────────────────────────────┘
                        │
         ┌──────────────▼──────────────┐
         │      backend.py (Engine)    │
         │                             │
         │  build_prompt()             │
         │  call_llm()                 │
         │  parse_csv_text()           │
         │  parse_json_objects()       │
         │  _execute_batch()           │
         │  generate_stream()          │
         └──────────────┬──────────────┘
                        │ OpenAI-compatible API
                        ▼
         ┌──────────────────────────────┐
         │  Databricks Serving Endpoint │
         │  Claude Sonnet 4.6           │
         └──────────────────────────────┘

         ┌──────────────────────────────┐
         │      profiler.py             │
         │  (Realistic tab only)        │
         │                             │
         │  list_tables()              │
         │  get_row_count()            │
         │  profile_databricks_table() │
         └──────────────┬──────────────┘
                        │ Databricks SQL connector
                        ▼
         ┌──────────────────────────────┐
         │  Databricks SQL Warehouse    │
         │  hive_metastore.ap_staging   │
         └──────────────────────────────┘
```

**Data flow summary:**
1. User configures settings in the UI
2. `app.py` builds a `DataGenBot` instance and calls `generate_stream()`
3. `generate_stream()` submits batches to a `ThreadPoolExecutor`
4. Each batch calls `build_prompt()` → `call_llm()` → `parse_csv_text()` or `parse_json_objects()`
5. Completed batches are yielded back to `app.py` as status dicts
6. `app.py` updates the progress bar, metrics, live preview, and logs
7. On completion, results are stored in `st.session_state` and download buttons appear

---

## 3. File Reference

| File | Role | Key Symbols |
|------|------|-------------|
| `app.py` | Streamlit UI, session state, progress, download | `run_generation()`, `render_saved_result()`, `main_tab_custom`, `main_tab_realistic` |
| `backend.py` | LLM client, prompt building, parsing, batching | `DataGenBot`, `build_realistic_prompt()`, `PROMPT_TEMPLATES`, `COLUMN_NAMES`, `OUTPUT_FORMATS`, `MAX_BATCH_SIZES` |
| `profiler.py` | Databricks table statistics | `profile_databricks_table()`, `list_tables()`, `get_row_count()` |
| `requirements.txt` | Python dependencies | `streamlit`, `openai`, `pandas`, `databricks-sql-connector`, `tiktoken`, `openpyxl` |
| `AGENTS.md` | Developer guide / coding conventions | Architecture notes, patterns, quirks |
| `synthetic_store_data.csv/.xlsx` | Example generated output | Reference only — not configuration |

---

## 4. Core Components — Deep Dive

### 4.1 `app.py` — Streamlit UI

#### Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `result_df` | `DataFrame \| None` | Final CSV output (Custom tab) |
| `result_json` | `list[dict] \| None` | Final JSON output (Custom tab) |
| `result_logs` | `list[str]` | Generation log lines (Custom tab) |
| `result_output_format` | `"csv" \| "json"` | Format of last run (Custom tab) |
| `result_element_type` | `str` | Data type label for display |
| `result_total_elapsed` | `float` | Wall-clock seconds for last run |
| `result_signature` | `dict` | Config hash — used to invalidate stale results |
| `realistic_profile` | `dict \| None` | Table profile from `profiler.py` |
| `realistic_tables` | `list[str] \| None` | Table names loaded from Databricks |
| `realistic_table_row_count` | `int \| None` | Exact row count from `get_row_count()` |
| `realistic_prompt_editor` | `str` | Cached text of the Step 3 rules editor |
| `realistic_result_*` | various | Mirror of `result_*` keys for Realistic tab |

#### Key Functions

**`run_generation(bot, result_prefix, element_label)`**  
Drives `bot.generate_stream()` in a loop, updating the Streamlit UI on each yielded status dict. Stores final results in session state under `result_prefix`.

**`render_saved_result(prefix)`**  
Reads results from session state and renders Preview / Logs / Download tabs. Called at the bottom of both main tabs so results persist across reruns.

**Token Budget Constants**

```python
REALISTIC_PROMPT_WARNING_TOKENS = 150_000   # soft UI warning threshold
REALISTIC_MODEL_CONTEXT_TOKENS  = 200_000   # Claude Sonnet full context window
_REALISTIC_MAX_SAFE_PROMPT      = 191_808   # 200,000 − 8,192 output cap
```

---

### 4.2 `backend.py` — Generation Engine

#### Prompt Templates

**`CLUSTER_PROMPT`** (CSV output)
```
Columns: STORE_NO, DEPT_NO, CSTD_GRADE, PHASE_STARTDATE
Rules:
- STORE_NO: 4-digit number, digits 1–9 only
- DEPT_NO: starts with G5- + 2–4 alphanumeric chars
- CSTD_GRADE: exactly 2 alphanumeric chars
- PHASE_STARTDATE: DD-MMM-YY format
```

**`PRODUCTVENDOR_PROMPT`** (JSON output)  
Produces nested JSON objects with `productId`, `season` (object), and `vendors` (array of objects).

#### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `MODEL_NAME` | `databricks-claude-sonnet-4-6` | LLM endpoint model ID |
| `_MAX_OUTPUT_TOKENS` | `8192` | Output token budget per LLM call |
| `MAX_BATCH_SIZES["Cluster"]` | `150` | CSV rows use ~15 tokens each |
| `MAX_BATCH_SIZES["ProductVendor"]` | `50` | Nested JSON uses ~80 tokens each |
| `MAX_BATCH_SIZES["RealisticTable"]` | `100` | Conservative default for wide tables |

#### `DataGenBot` Class

```python
DataGenBot(
    model_name,       # LLM model ID
    api_key,          # overwritten by hardcoded Databricks token
    base_url,         # overwritten by hardcoded Databricks endpoint
    data_type,        # "Cluster" | "ProductVendor" | "RealisticTable"
    num_rows,         # total rows to generate
    batch_size,       # rows per LLM call (auto-capped)
    custom_prompt,    # user-edited rules text (optional)
    parallelism,      # concurrent API calls (1–8, default 3)
    temperature,      # LLM randomness (0.0–1.0, default 0.7)
    column_names,     # override column list (for RealisticTable)
    profile,          # table profile dict (for RealisticTable)
)
```

**`build_prompt(batch_size)`** — Prompt priority order:
1. If `data_type == "RealisticTable"` and `_profile` is set → calls `build_realistic_prompt()`
2. If `custom_prompt` is set → prepends the batch-size header and appends user rules
3. Otherwise → uses the static `PROMPT_TEMPLATES[data_type]`

**`generate_stream()`** — Generator flow:
```
1. Compute num_batches = ceil(num_rows / batch_size)
2. Submit all batches to ThreadPoolExecutor (parallelism workers)
3. As each batch completes → yield partial status dict
4. After all batches → enter top-up loop (max 10 attempts) for any shortfall
5. Final yield with done=True, final_df/final_json
```

**Status dict shape (yielded by `generate_stream()`):**
```python
{
    "batch_num":    int,        # completed batches so far
    "num_batches":  int,        # total planned batches
    "logs":         list[str],  # all log lines so far
    "output_format": "csv" | "json",
    "partial_df":   DataFrame | None,
    "partial_json": list[dict] | None,
    "done":         bool,
    "final_df":     DataFrame | None,   # only set when done=True
    "final_json":   list[dict] | None,  # only set when done=True
    "elapsed_last": float,      # seconds for last completed batch
}
```

---

### 4.3 `profiler.py` — Table Profiler

#### Connection defaults

```python
DATABRICKS_HOST      = "adb-4224005571705028.8.azuredatabricks.net"
DATABRICKS_HTTP_PATH = "/sql/1.0/warehouses/99afececa9e21495"
DATABRICKS_CATALOG   = "hive_metastore"
DATABRICKS_SCHEMA    = "ap_staging_sit"
```

#### `profile_databricks_table()` — 4-query strategy

| Step | Query | Purpose |
|------|-------|---------|
| 1 | `SELECT COUNT(*)` | Exact full-table row count (from metadata, fast) |
| 2 | `DESCRIBE TABLE` | Column names and types, zero data scan |
| 3 | Single aggregation on `TABLESAMPLE(N ROWS)` | MIN, MAX, APPROX_COUNT_DISTINCT, NULL count, AVG (numeric), TRUE count (boolean) |
| 4 | `GROUP BY … ORDER BY freq DESC LIMIT N` per string column | Top-N most frequent values with frequency % |

#### Smart fetch limit for string columns

```python
# If approx distinct count ≤ top_values: fetch a larger limit to capture ALL values
fetch_limit = top_values if card > top_values else int(card * 1.5 + 10)
```

This ensures low-cardinality columns (e.g., 66 distinct grades) are fully fetched even when `top_values` is set high.

#### Profile dict structure

```python
{
    "table":       "hive_metastore.schema.table_name",
    "row_count":   int,          # exact count
    "sample_rows": int,          # actual TABLESAMPLE size
    "columns": [
        {
            "name":     "STORE_NO",
            "dtype":    "string",
            "kind":     "string",   # numeric | date | boolean | string | other
            "nullable": False,
            "null_pct": 0.0,
            # string columns also have:
            "distinct_count": 706,  # APPROX_COUNT_DISTINCT (estimate)
            "top_values": [
                {"value": "6460", "freq_pct": 0.7},
                ...
            ]
        },
        # numeric columns have: min, max, mean
        # date columns have: min_date, max_date
        # boolean columns have: true_pct
    ]
}
```

---

## 5. Data Types & Output Formats

### Cluster (CSV)

| Column | Type | Rule |
|--------|------|------|
| `STORE_NO` | string | 4-digit number, digits 1–9 only |
| `DEPT_NO` | string | `G5-` prefix + 2–4 alphanumeric chars |
| `CSTD_GRADE` | string | Exactly 2 alphanumeric characters |
| `PHASE_STARTDATE` | string | `DD-MMM-YY` format (e.g. `29-Jun-25`) |

Output: raw CSV rows, no header, downloaded as `.csv` or `.xlsx`.

### ProductVendor (JSON)

Nested JSON with three levels:
```json
{
    "productId": "000000000006059884",
    "season": {
        "seasonYear": "2025",
        "seasonName": "SP25"
    },
    "vendors": [
        {
            "supplierNumber": "M00055",
            "factoryNumber":  "10000142750",
            "isActive":       "true"
        }
    ]
}
```

Output: JSON array, downloaded as `.json`.

### RealisticTable (CSV)

Dynamic — columns and rules are derived entirely from the profiled Databricks table. Output always CSV.

---

## 6. Generation Pipeline — Step by Step

```
User clicks "🚀 Generate Data"
        │
        ▼
DataGenBot initialised
  - batch_size auto-capped to MAX_BATCH_SIZES[data_type]
  - num_batches = ceil(num_rows / batch_size)
        │
        ▼
ThreadPoolExecutor submits all batches simultaneously
  (up to parallelism workers running at once)
        │
        ├── Batch 1 ──► build_prompt(bs) ──► call_llm() ──► parse()
        ├── Batch 2 ──► build_prompt(bs) ──► call_llm() ──► parse()
        └── Batch N ──► ...
              │
              │  Each batch: up to 3 retry attempts
              │  On parse failure: log error, try again
              │  After 3 failures: skip batch, log warning
              │
              ▼
        as_completed() yields each finished batch
              │
              ▼
        app.py updates: progress bar, metrics, live preview, logs
              │
              ▼ (all batches done)
        Top-up loop (max 10 attempts)
          while actual_rows < num_rows:
              request shortfall rows in a new batch
              append to results
              break if batch keeps failing
              │
              ▼
        Final yield (done=True)
          - Concatenate all DataFrames / JSON lists
          - Trim to exactly num_rows
          - Store in st.session_state
          - Download buttons appear
```

---

## 7. Realistic Table Generation Flow

```
Step 1 — Select Table
  ├─ "🔄 Load Tables" → list_tables() → SHOW TABLE EXTENDED (managed only)
  ├─ "📊 Check Row Count" → get_row_count() → SELECT COUNT(*)
  └─ Set "📐 Profile Sample Size" (default 10,000 rows)

Step 2 — Profile Table
  └─ "🔍 Profile Table" → profile_databricks_table()
       ├─ COUNT(*) full table
       ├─ DESCRIBE TABLE (schema)
       ├─ Single aggregation TABLESAMPLE scan
       └─ Per-string-column GROUP BY frequency scan

Step 2b — Distinct Value Coverage Review
  ├─ Shows each string column: distinct count + how many values were fetched
  ├─ Tolerance band: if gap ≤ max(5, 5% of approx count) → "✅ ~all fetched"
  ├─ "🔤 Max Distinct Values per String Column" input (default 200, max 1000)
  └─ "🔄 Re-profile with updated limit"
       ├─ Calls profile_databricks_table(top_values=new_limit)
       ├─ Updates st.session_state["realistic_profile"]
       ├─ Explicitly writes new prompt to st.session_state["realistic_prompt_editor"]
       └─ st.rerun() → Step 3 shows updated prompt

Step 3 — Review / Edit Generated Prompt
  ├─ Auto-built from profile via build_realistic_prompt()
  ├─ "Generate exactly N rows…" header stripped — re-injected at runtime
  ├─ Token Budget Panel (colour-coded progress bar vs 150k soft limit)
  └─ User can edit any rule before generating

Step 4 — Generation Settings
  ├─ Total Rows, Batch Size, Parallel Calls, Temperature
  └─ Effective batch size = min(batch_size, MAX_BATCH_SIZES["RealisticTable"])

Step 5 — Generate
  └─ DataGenBot(profile=_profile) → generate_stream() → CSV output
```

---

## 8. Token Budget System

Claude Sonnet 4.6 supports:
- **Input (context) window:** 200,000 tokens
- **Output per call:** max 8,192 tokens (explicitly set via `max_tokens=8192`)

The UI shows a **Token Budget Panel** between Steps 3 and 4:

| Metric | Value |
|--------|-------|
| Prompt tokens (estimated) | Live estimate using `tiktoken` cl100k_base |
| Soft warning threshold | 150,000 tokens |
| Hard context limit | 200,000 tokens |
| Output cap per call | 8,192 tokens |
| Context remaining | 200,000 − prompt tokens |

**Colour coding:**
- 🟢 Green — below 60% of warning threshold
- 🟡 Amber — 60%–100% of warning threshold
- 🔴 Red — above 150,000 tokens

**Token estimation fallback:** If `tiktoken` is not installed, falls back to `ceil(len(text) / 4)` (character-based estimate).

**Why `max_tokens=8192` is set explicitly:**  
Without it, the Databricks serving endpoint defaults to ~1,024 output tokens — guaranteed truncation for any meaningful batch. Setting it to 8,192 gives the model its full output budget every call.

---

## 9. Distinct Value Coverage System

When profiling string columns, two sources of information are combined:

| Source | How obtained | Accuracy |
|--------|-------------|---------|
| `distinct_count` | `APPROX_COUNT_DISTINCT()` SQL function | ±2–5% approximation |
| `top_values` length | Actual `GROUP BY … LIMIT N` result | Exact (but limited to sample rows) |

#### Why gaps appear

`APPROX_COUNT_DISTINCT` uses a probabilistic algorithm (HyperLogLog) — it can over-estimate slightly. Additionally, a `TABLESAMPLE(10,000 ROWS)` may not contain every distinct value from the full table.

#### Coverage labels

| Condition | Label |
|-----------|-------|
| `fetched >= approx_count` | ✅ all fetched |
| `fetched >= approx_count − max(5, 5% of approx_count)` | ✅ ~all fetched (within approximation margin) |
| All other cases | ⚠️ `N / ~M fetched` — increase limit & re-profile |

#### Smart fetch limit (profiler)

```python
fetch_limit = top_values if card > top_values else int(card * 1.5 + 10)
```

When `APPROX_COUNT_DISTINCT ≤ top_values`, the query fetches `card * 1.5 + 10` rows — well above the approximate count — ensuring all real distinct values are captured even with approximation error.

---

## 10. Batch & Retry Logic

### Batch sizing

```python
num_batches = ceil(num_rows / batch_size)
# Last batch may be smaller:
batch_sizes = [min(batch_size, remaining) for each batch]
```

### Per-batch retry (up to 3 attempts)

```
Attempt 1 → call_llm() → parse()
  ✔ Success → store result, break
  ✖ Failure → log error, retry
Attempt 2 → same
Attempt 3 → same
  ✖ After 3 failures → log "⚠ Skipping batch N", mark as failed
```

Failures can come from:
- API timeout / rate limit
- LLM returning wrong number of rows/objects
- LLM returning malformed JSON/CSV
- Wrong number of columns in CSV output

### Top-up loop

After all main batches complete:
```python
while shortfall > 0 and topup_attempt < 10:
    request min(shortfall, batch_size) extra rows
    append to results if successful
    break if batch keeps failing (3 retries each)
```

The final output is always trimmed to exactly `num_rows`:
```python
final_df = pd.concat(all_dfs).head(num_rows)
final_json = flat_all[:num_rows]
```

---

## 11. Configuration Reference

### Sidebar settings (Custom Generation tab only)

| Setting | Range | Default | Effect |
|---------|-------|---------|--------|
| Element Type | Cluster / ProductVendor | Cluster | Selects prompt template and output format |
| Total Rows | 10 – 10,000 | 1,000 | Total records to generate |
| Batch Size | 10 – 200 | 100 | Rows per LLM call (auto-capped by type) |
| Parallel API Calls | 1 – 5 | 3 | Concurrent LLM calls |
| Temperature | 0.0 – 1.0 | 0.7 | LLM randomness (lower = fewer duplicates) |

### Realistic tab inline settings (Step 4)

| Setting | Range | Default | Effect |
|---------|-------|---------|--------|
| Profile Sample Size | 1,000 – 100,000 | 10,000 | Rows sampled for statistics |
| Max Distinct Values | 10 – 1,000 | 200 | String values fetched per column for prompt |
| Total Rows | 10 – 10,000 | 500 | Synthetic rows to generate |
| Batch Size | 10 – 150 | 50 | Rows per LLM call |
| Parallel Calls | 1 – 5 | 3 | Concurrent LLM calls |
| Temperature | 0.0 – 1.0 | 0.7 | LLM randomness |

### Hard-coded constants (backend.py / profiler.py)

| Constant | Value | Location |
|----------|-------|---------|
| Databricks host | `adb-4224005571705028.8.azuredatabricks.net` | Both files |
| Databricks token | `dapi7ea...` | Both files |
| SQL warehouse HTTP path | `/sql/1.0/warehouses/99afececa9e21495` | `profiler.py` |
| Catalog | `hive_metastore` | `profiler.py` |
| Schema | `ap_staging_sit` | `profiler.py` |
| Model name | `databricks-claude-sonnet-4-6` | `backend.py` |
| Max output tokens | `8192` | `backend.py` |

---

## 12. Databricks Integration

### LLM Serving Endpoint

Uses the **OpenAI-compatible client** (`openai.OpenAI`) pointed at the Databricks serving endpoint:

```python
client = OpenAI(
    api_key  = "dapi7ea...",
    base_url = "https://adb-4224005571705028.8.azuredatabricks.net/serving-endpoints"
)
response = client.chat.completions.create(
    model       = "databricks-claude-sonnet-4-6",
    messages    = [{"role": "system", ...}, {"role": "user", ...}],
    temperature = 0.7,
    max_tokens  = 8192,
)
```

### SQL Warehouse (Profiler)

Uses the `databricks-sql-connector`:

```python
conn = dbsql.connect(
    server_hostname = DATABRICKS_HOST,
    http_path       = DATABRICKS_HTTP_PATH,
    access_token    = DATABRICKS_TOKEN
)
```

Only **managed tables** are listed (external tables and views are excluded via `SHOW TABLE EXTENDED` filtering on `"Type: MANAGED"`).

---

## 13. How to Run

### Prerequisites
- Python virtual environment in `venv\Scripts\`
- Databricks workspace accessible from the machine
- All dependencies installed

### Start the app

```powershell
# From the repo root
venv\Scripts\python.exe -m streamlit run app.py
```

### Reinstall dependencies

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Key dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `openai` | OpenAI-compatible LLM client |
| `pandas` | DataFrame parsing and CSV handling |
| `databricks-sql-connector` | Databricks SQL warehouse connection |
| `tiktoken` | Accurate token counting (optional) |
| `openpyxl` | Excel download support |

---

## 14. How to Add a New Data Type

Adding a new type (e.g., `OrderLine`) requires changes in **three places**:

### Step 1 — `backend.py`

```python
# 1. Add prompt template
ORDERLINE_PROMPT = """
Generate exactly {batch_size} UNIQUE CSV rows.
Columns: ORDER_ID,PRODUCT_SKU,QTY,UNIT_PRICE
Rules:
- ORDER_ID: ...
...
"""

# 2. Register in all three dicts
PROMPT_TEMPLATES["OrderLine"] = ORDERLINE_PROMPT
COLUMN_NAMES["OrderLine"]     = ["ORDER_ID", "PRODUCT_SKU", "QTY", "UNIT_PRICE"]
OUTPUT_FORMATS["OrderLine"]   = "csv"           # or "json"
MAX_BATCH_SIZES["OrderLine"]  = 100             # tune based on output token cost
```

### Step 2 — `app.py`

```python
# Add to the sidebar selectbox options
data_type = st.selectbox(
    "Element Type",
    options=["Cluster", "ProductVendor", "OrderLine"],  # ← add here
    ...
)
```

### Step 3 — If JSON output: update `parse_json_objects()` in `backend.py`

Add validation for the new JSON schema's required keys (the current implementation validates `productId`, `season`, and `vendors`).

---

## 15. Demo Q&A — Common Questions

This section covers questions that typically arise when demonstrating the tool.

---

### General Questions

**Q: Is this pulling real data from our production systems?**  
A: No. The LLM generates data completely from scratch based on rules in the prompt. For the Realistic tab, we profile the table's *statistics* (ranges, value frequencies, null rates) — no actual production rows are sent to the LLM or leave your environment.

**Q: Where does the LLM run? Is our data leaving the company?**  
A: The LLM (Claude Sonnet 4.6) runs on your Databricks workspace on Azure — it stays within your Azure tenant and is subject to your existing data governance controls. Only the prompt text (statistical rules, not actual data) is sent to the model.

**Q: How fast is it? Can it generate 10,000 rows?**  
A: With 3 parallel calls and batch size 100, you get roughly 3–5 seconds per parallel round. For 10,000 rows that's ~70 batches ÷ 3 parallel = ~23 rounds × ~4s ≈ 90–120 seconds. The progress bar and live record count show real-time progress.

**Q: How unique is the generated data? Will there be duplicates?**  
A: Each batch prompt instructs the model to generate UNIQUE rows within that batch. Across batches, occasional duplicates are possible since the model has no memory of previous batches. For most use cases (testing, demo data) this is acceptable. Temperature controls randomness — lower values reduce duplicates.

---

### Custom Generation Tab

**Q: What is the "Batch Size" and why does it get capped?**  
A: Batch size is how many rows we ask the LLM to produce in a single API call. The LLM has a hard output limit of 8,192 tokens per call. A Cluster CSV row uses ~15 tokens (safe up to 150 rows/batch) while a ProductVendor JSON object uses ~80 tokens (safe up to 50/batch). Exceeding the cap risks truncated output, so the app automatically enforces the limit.

**Q: Can I customise the data rules?**  
A: Yes — the prompt editor in the UI is fully editable. You can change value ranges, add new constraints, or modify field formats. The batch-size header is injected automatically so you don't need to manage that.

**Q: Why does the prompt in the editor not say "Generate exactly N rows"?**  
A: That line is stripped from the display intentionally — it's re-injected by the backend at runtime with the correct batch size. This prevents confusion when editing rules.

**Q: What happens if a batch fails?**  
A: Each batch gets up to 3 retry attempts. If all 3 fail, the batch is skipped and logged. A top-up loop then requests the missing rows in additional batches. You can inspect failures in the 📋 Logs tab after generation.

---

### Realistic Table Generation Tab

**Q: What does "Profile Table" actually do?**  
A: It runs 4 SQL queries against your Databricks table:
1. `COUNT(*)` — exact row count
2. `DESCRIBE TABLE` — column names and types
3. A single aggregation query on a random sample (MIN, MAX, distinct count, null rate, average)
4. A `GROUP BY` frequency query per string column to get the top-N most common values with their real percentages

**Q: Why does it only sample 10,000 rows by default? Will that be accurate enough?**  
A: For most distributions, 10,000 rows is statistically sufficient to capture value frequencies, ranges, and null rates. For very skewed distributions or rare values, you can increase the sample size (up to 100,000). The profile sample size only affects statistics quality — not how many synthetic rows are generated.

**Q: What is the "Max Distinct Values per String Column" setting?**  
A: It controls how many distinct string values are fetched from the database per string/categorical column and injected into the LLM prompt. For example, if `STORE_NO` has 706 distinct values and you set this to 500, the LLM will be given the top 500 most frequent store numbers (with their real frequency %). If a column has fewer distinct values than the limit, all of them are fetched automatically.

**Q: My column shows ⚠️ even after I increased the limit. Is something wrong?**  
A: Likely not. The `~N distinct` count comes from `APPROX_COUNT_DISTINCT`, which is a probabilistic SQL function accurate to ±2–5%. If a column shows "64 / ~66 fetched", it almost certainly means all 64 values in the sample have been captured and the SQL estimate is slightly off. The app applies a tolerance band (max of 5 values or 5%) before flagging a genuine ⚠️ warning.

**Q: Why do I need to click "Re-profile" after changing the Max Distinct Values?**  
A: The distinct values are fetched from Databricks SQL during profiling — they're not recalculated on the fly. Changing the limit and clicking Re-profile re-runs the GROUP BY queries with the new LIMIT, fetches more values, and automatically rebuilds the Step 3 prompt with the updated list.

**Q: Can I edit the prompt after profiling?**  
A: Yes. Step 3 shows a fully editable text area. You can add business constraints (e.g., "STORE_NO must start with 1 or 2"), remove columns, tighten ranges, or add cross-column rules. Any edits you make are used for generation and override the auto-built profile rules.

**Q: The token budget panel shows I'm using a lot of tokens. Is that a problem?**  
A: As long as you're below the 150,000 soft warning (shown in the progress bar), you're fine. Claude Sonnet 4.6 has a 200,000 token context window and we reserve 8,192 for output, leaving ~191,808 for the prompt. High token counts typically come from columns with many distinct values — this is intentional and makes the output more realistic.

**Q: Why doesn't the Realistic tab use the sidebar settings?**  
A: The sidebar applies only to the Custom Generation tab. Realistic tab has its own inline settings (Step 4) because the relevant parameters — batch size, parallelism, temperature — are configured in-context alongside the profile and prompt, making the workflow self-contained.

---

### Output & Download

**Q: What download formats are available?**  
A: CSV and Excel (`.xlsx`) for all CSV-output types. JSON for ProductVendor. Excel download uses `openpyxl` and includes a `SyntheticData` worksheet.

**Q: Can I generate more than 10,000 rows?**  
A: The UI caps at 10,000 rows per run by default. This is a UI guard — the backend has no hard limit. For larger volumes, you can run the tool multiple times and concatenate the outputs, or modify the `max_value=10000` in the `st.number_input` call in `app.py`.

**Q: If the LLM returns fewer rows than requested, does the tool compensate?**  
A: Yes. The top-up loop runs after all main batches and requests additional rows until the target is met (up to 10 top-up attempts). If rows are still missing after all attempts, the final output contains however many were generated, with a warning in the logs.

---

### Performance & Scaling

**Q: What's the maximum parallelism supported?**  
A: The UI allows 1–5 parallel calls. The backend clamps to 1–8. Higher parallelism is faster but increases load on the Databricks serving endpoint. If you see rate-limit errors, reduce to 1–2 parallel calls.

**Q: How do I estimate total generation time?**  
A: `est_time ≈ ceil(num_batches / parallelism) × avg_seconds_per_batch`  
Typical batch times: ~3–5s for Cluster CSV, ~5–8s for ProductVendor JSON, ~4–8s for Realistic Table.  
The UI shows estimated batches and parallel rounds in the sidebar/Step 4 summary.

**Q: Can this be run headlessly without the Streamlit UI?**  
A: Yes. `DataGenBot` is a standalone class. You can instantiate it and call `generate_stream()` directly from any Python script:
```python
from backend import DataGenBot
bot = DataGenBot(model_name="databricks-claude-sonnet-4-6", ..., data_type="Cluster", num_rows=1000, batch_size=100)
for status in bot.generate_stream():
    if status["done"]:
        df = status["final_df"]
        df.to_csv("output.csv", index=False)
```

---

### Security & Governance

**Q: Where are the credentials stored?**  
A: Currently hardcoded in `backend.py` and `profiler.py`. For production use, these should be moved to environment variables or Databricks secrets.

**Q: Does the tool write anything back to Databricks?**  
A: No. The profiler only reads from Databricks (SELECT / DESCRIBE / SHOW queries). No data is written. All generated data lives in the Streamlit session and is only persisted if the user downloads it.

**Q: Can this tool be used on PII or sensitive tables?**  
A: The profiler sends statistical summaries (value frequencies, ranges) — not actual rows — to the LLM. However, if a string column has very few distinct values (e.g., a 2-value status flag), those exact values will appear in the prompt. Review the generated prompt in Step 3 before generating if the table contains sensitive categories.

---

*End of Technical Documentation*

