# AGENTS.md

## Project purpose
- This repo is a small synthetic-data generator driven by LLM calls. The main user-facing flow is `app.py` (Streamlit UI) calling `backend.py` (prompting, batching, parsing, validation).
- Two data types are currently wired end-to-end: `Cluster` and `ProductVendor`.

## Big picture architecture
- `app.py` owns the UI, Streamlit session state, progress bar, preview, and download buttons.
- `backend.py` owns prompt templates, LLM client setup, response cleanup, CSV/JSON parsing, and batch retry logic.
- UI → backend flow: `app.py` calls `get_editable_prompt(data_type)`, builds `DataGenBot(...)`, then iterates `for status in bot.generate_stream():`.
- `generate_stream()` yields incremental status dicts with `batch_num`, `logs`, `output_format`, partial results, and final results; `app.py` consumes these to update progress and save the final payload in `st.session_state`.
- Output format is type-specific: `Cluster` is parsed into a `pandas.DataFrame`; `ProductVendor` stays as nested JSON objects.

## Files that matter
- `app.py`: Streamlit page layout, sidebar config, prompt editor, run button, `render_saved_result()`.
- `backend.py`: `PROMPT_TEMPLATES`, `COLUMN_NAMES`, `OUTPUT_FORMATS`, `get_editable_prompt()`, `DataGenBot`.
- `LLM_DEMO-CLUSTER.py`: older notebook-style prototype for CSV generation against Databricks.
- `example.py`: older Gemini-based JSON generator; useful as reference, not part of the Streamlit app path.
- `synthetic_store_data.csv` / `synthetic_store_data.xlsx`: sample/generated artifacts, not source-of-truth configuration.

## Project-specific patterns and conventions
- The prompt shown in the UI is intentionally not the literal backend prompt. `get_editable_prompt()` strips the leading “Generate exactly {batch_size} ...” instructions, and `DataGenBot.build_prompt()` re-injects the batch size at runtime.
- If you add a new data type, update all of these together: `PROMPT_TEMPLATES`, `COLUMN_NAMES`, `OUTPUT_FORMATS` in `backend.py`, plus the `options=[...]` list in `app.py`.
- JSON generation expects an array fragment, not a full array. `parse_json_objects()` removes surrounding `[` / `]`, wraps the fragment back into `[...]`, then validates nested keys like `season` and `vendors`.
- CSV generation assumes raw rows with no header. `parse_csv_text()` always supplies column names from `COLUMN_NAMES`.
- `render_saved_result()` branches on `result_output_format`; keep that contract if you add new output types.
- Result persistence is in Streamlit session state under keys like `result_df`, `result_json`, and `result_logs`.

## Integration points and quirks
- The LLM call uses the OpenAI-compatible client in `backend.py` (`OpenAI(...).chat.completions.create(...)`) against a Databricks serving endpoint, not the public OpenAI API.
- Credentials/model endpoint are hardcoded in multiple places: `app.py`, `backend.py`, `LLM_DEMO-CLUSTER.py`, and `example.py`. In `DataGenBot.__init__`, the passed `api_key` and `base_url` are overwritten by hardcoded values before the client is created.
- Retry behavior is local to each batch: `generate_stream()` retries each batch up to 2 times, logs failures, and can continue after a skipped batch.

## Developer workflows
- Use the local venv in `venv\Scripts\`. `streamlit.exe` and `python.exe` are present there.
- Main app run command from repo root:
  - `venv\Scripts\python.exe -m streamlit run app.py`
- Dependency install command if recreating the environment:
  - `venv\Scripts\python.exe -m pip install -r requirements.txt`
- There is no automated test suite in the repo. The practical regression check is to run the Streamlit app and verify both `Cluster` (CSV preview/download) and `ProductVendor` (JSON preview/download) paths.
- For debugging generation failures, inspect the UI log expander fed by `status["logs"]`; exceptions are also surfaced with `st.exception(e)` in `app.py`.

## When editing
- Preserve the status-dict shape returned by `generate_stream()`; `app.py` depends on keys such as `done`, `final_df`, `final_json`, and `output_format`.
- Keep prompts and parsers in sync. Example: if you change the `ProductVendor` JSON schema in `PRODUCTVENDOR_PROMPT`, also update validation in `parse_json_objects()`.
- Treat `LLM_DEMO-CLUSTER.py` and `example.py` as reference scripts unless the task explicitly asks to modernize them alongside the app.

