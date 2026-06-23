# Synthetic Data Generation Agent — Project Overview

## Problem Statement
`Enterprise teams constantly need realistic datasets for development, testing, and analytics, but using production data exposes sensitive customer information and creates compliance risks. Manually crafting synthetic data is slow, error-prone, and doesn't scale — blocking pipelines before real data is ever available.
`
## Solution
`A Streamlit-based AI agent that leverages Claude Sonnet via Databricks to generate schema-validated synthetic datasets on demand. Users configure data type, row count, and batch size through the UI — the agent handles prompting, parsing, validation, and retry automatically, delivering results as CSV or JSON with one-click download.
`
## Challenges
- **Production data is off-limits** — PII, regulatory constraints, and access controls make it impractical to share or replicate real datasets across teams.
- **LLM output is unpredictable** — raw model responses require strict parsing, schema validation, and retry logic to guarantee field-level correctness (formats, uniqueness, nesting).
- **Scale without quality loss** — generating thousands of rows in batches while maintaining consistency across fields (e.g. unique STORE_NO + DEPT_NO combos) is non-trivial.
- **Multi-format complexity** — CSV and nested JSON outputs demand separate parsing pipelines and validation rules that must stay in sync with prompt templates.

## Benefits
- **Zero PII risk** — fully synthetic data means no compliance overhead; share freely across dev, QA, and vendor teams.
- **On-demand at scale** — batch-streaming architecture with auto-retry delivers 10,000+ rows in a single run with live progress visibility.
- **No-code flexibility** — prompts and parameters are editable in the UI; adding a new data type requires changes in only three places in the codebase.
- **Portable & extensible** — OpenAI-compatible client makes it trivial to swap Databricks for Azure OpenAI or any other endpoint without rewriting the app.

