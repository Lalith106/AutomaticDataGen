from openai import OpenAI
import pandas as pd
import io
import math
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

try:
    import tiktoken  # optional; used for a more accurate prompt-token estimate when available
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None

# ── Default prompt templates per data type ──────────────────────────────────

CLUSTER_PROMPT = """
Generate exactly {batch_size} UNIQUE CSV rows.

Columns: STORE_NO,DEPT_NO,CSTD_GRADE,PHASE_STARTDATE

Rules:
- STORE_NO: 4-digit number,digits 1–9 only (e.g. 1238). Do NOT repeat STORE_NO within this batch.
- DEPT_NO: starts with G5- followed by 2–4 alphanumeric characters (e.g. G5-AB12). Do NOT repeat DEPT_NO within this batch.
- CSTD_GRADE: exactly 2 alphanumeric characters (e.g. A1).
- PHASE_STARTDATE: format DD-MMM-YY (e.g. 29-Jun-25).
- NO quotes, NO commentary, NO headers, NO blank lines.
- Output ONLY raw CSV rows, nothing else.
"""

PRODUCTVENDOR_PROMPT = """
Generate exactly {batch_size} UNIQUE JSON objects, formatted as a JSON array fragment.
Do NOT include the opening '[' or closing ']' brackets in your output.
Each object must strictly adhere to the NESTED structure and fields shown in the example:

{{
"productId": "...",
"season": {{
    "seasonYear": "...",
    "seasonName": "..."
}},
"vendors": [
    {{
        "supplierNumber": "...",
        "factoryNumber": "...",
        "isActive": "..."
    }}
]
}}

Rules for generating data:
- productId: Must be a unique, 18-digit string, padded with leading zeros (e.g., "0000000000060598841").
- seasonYear: A 4-digit year string (e.g., "2024", "2025").
- seasonName: A unique alphanumeric code (e.g., "SP24", "FA25").
- supplierNumber: A unique 6-character code starting with 'M' (e.g., "M00055").
- factoryNumber: A unique 11-digit string (e.g., "1000014275").
- isActive: Must be a boolean string ("true" or "false").
- Ensure each top-level object is separated by a comma.
- Output ONLY the raw JSON array fragment, with NO commentary, NO explanations, and NO surrounding text.
"""

PROMPT_TEMPLATES = {
    "Cluster": CLUSTER_PROMPT,
    "ProductVendor": PRODUCTVENDOR_PROMPT,
}

COLUMN_NAMES = {
    "Cluster": ["STORE_NO", "DEPT_NO", "CSTD_GRADE", "PHASE_STARTDATE"],
    "ProductVendor": ["PRODUCT_ID", "VENDOR_ID", "PRODUCT_NAME", "VENDOR_NAME", "UNIT_PRICE", "STOCK_QTY"],
    "RealisticTable": [],   # populated dynamically from table profile at generation time
}

OUTPUT_FORMATS = {
    "Cluster": "csv",
    "ProductVendor": "json",
    "RealisticTable": "csv",
}

# Safe upper bound for batch size per data type.
MAX_BATCH_SIZES = {
    "Cluster": 150,       # CSV rows are tiny (~15 tokens each)
    "ProductVendor": 50,  # Nested JSON objects are ~80 tokens each; cap keeps output clean
    "RealisticTable": 100,   # conservative default; user can tune per table width
}

# max_tokens controls the OUTPUT token budget for each LLM call.
# It has nothing to do with the context/input window.
#
# Why we set it explicitly instead of leaving it unset:
#   The Databricks serving endpoint defaults to ~1024 output tokens when
#   max_tokens is omitted — far too low for any non-trivial batch and a
#   guaranteed source of truncation.
#
# Why 8192:
#   Claude Sonnet 4.5 / 4.6 supports a maximum of 8 192 output tokens per
#   call. Setting this value gives the model its full output budget on every
#   batch regardless of data type. Going higher than 8192 has no effect and
#   some endpoints will reject the request.
#
#   Rule of thumb for other models:
#     Llama 3.x / Mixtral / DBRX → typically 4 096 output tokens max
#     If you switch models and see truncation, lower this to 4096.
_MAX_OUTPUT_TOKENS = 8192

# Public alias for UI code that wants to display the current generation cap.
MAX_OUTPUT_TOKENS = _MAX_OUTPUT_TOKENS

MODEL_NAME = "databricks-claude-opus-4-8"


def get_output_format(data_type: str) -> str:
    return OUTPUT_FORMATS.get(data_type, "csv")


def get_editable_prompt(data_type: str) -> str:
    template = PROMPT_TEMPLATES.get(data_type, CLUSTER_PROMPT).strip()
    lines = template.splitlines()

    removable_prefixes = (
        "Generate exactly {batch_size}",
        "Do NOT include the opening '[' or closing ']' brackets in your output.",
    )

    while lines and (not lines[0].strip() or any(lines[0].strip().startswith(prefix) for prefix in removable_prefixes)):
        lines.pop(0)

    return "\n".join(lines).strip()


def estimate_token_count(text: str) -> int:
    """
    Approximate token count for a prompt or response.

    Uses tiktoken's cl100k_base encoding when available, otherwise falls back to
    a simple character-based estimate that is good enough for UI warnings.
    """
    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            pass

    return max(1, math.ceil(len(text) / 4))


def build_realistic_prompt(profile: dict, batch_size: int) -> str:
    """
    Convert a table profile dict (from profiler.py) into a detailed, per-column
    LLM prompt that drives realistic CSV generation.

    The returned prompt already starts with the 'Generate exactly N rows' header
    so it is ready to be passed directly as *custom_prompt* to DataGenBot
    (which will NOT prepend anything extra when custom_prompt is set).
    """
    table_name  = profile.get("table", "unknown_table")
    columns     = profile.get("columns", [])
    col_names   = [c["name"] for c in columns]
    col_list    = ", ".join(col_names)

    lines = [
        f"Generate exactly {batch_size} UNIQUE CSV rows that faithfully mimic "
        f"production data from table `{table_name}`.",
        "",
        f"Columns (in this exact order): {col_list}",
        "",
        "Rules per column:",
    ]

    for col in columns:
        name     = col["name"]
        kind     = col.get("kind", "other")
        dtype    = col["dtype"]
        nullable = col.get("nullable", False)
        null_pct = col.get("null_pct", 0.0)

        rule = f"- {name} ({dtype}): "

        if kind == "numeric":
            mn, mx, mean = col.get("min"), col.get("max"), col.get("mean")
            rule += f"number in range [{mn}, {mx}]"
            if mean is not None:
                rule += f"; typical average ≈ {mean}"

        elif kind == "date":
            rule += (
                f"date/timestamp between {col.get('min_date')} "
                f"and {col.get('max_date')}"
            )

        elif kind == "boolean":
            tp = col.get("true_pct", 50)
            rule += f"boolean (true / false); approximately {tp}% of values should be true"

        elif kind == "string":
            tv      = col.get("top_values", [])   # [{"value": ..., "freq_pct": ...}]
            d_count = col.get("distinct_count", 0)
            if tv:
                # Show value + frequency so the LLM mirrors the real distribution.
                # No artificial slice — the profiler already caps to `top_values`
                # (default 200) and fetches ALL values for low-cardinality columns.
                quoted = ", ".join(
                    f'"{e["value"]}" ({e["freq_pct"]}%)'
                    if e.get("freq_pct") is not None
                    else f'"{e["value"]}"'
                    for e in tv
                )
                rule += f"must be one of (shown with % frequency from production sample): [{quoted}]"
                if d_count > len(tv):
                    rule += (
                        f"  … (~{d_count:,} distinct values total; "
                        f"vary within the spirit of those shown, weighted by frequency)"
                    )
            else:
                rule += f"free-form string with ~{d_count:,} distinct values; generate realistic examples"

        else:
            samples = col.get("samples", [])
            rule += f"value similar to these samples: {samples}" if samples else "generate a realistic value"

        if nullable and null_pct > 0:
            rule += f"  [nullable — leave empty for approximately {null_pct}% of rows]"

        lines.append(rule)

    lines += [
        "",
        "General rules:",
        "- Produce realistic, varied data that resembles the production distribution.",
        "- Do NOT repeat the same value for every row in a column.",
        "- Respect null/empty rules: leave the cell empty (no text) when a column is nullable.",
        "- NO column headers, NO commentary, NO markdown, NO blank lines.",
        "- Output ONLY raw CSV rows separated by commas, nothing else.",
    ]

    return "\n".join(lines)


class DataGenBot:
    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str,
        data_type: str,
        num_rows: int,
        batch_size: int,
        custom_prompt: str = "",
        parallelism: int = 3,
        temperature: float = 0.7,
        column_names: list = None,   # override static COLUMN_NAMES for dynamic types
        profile: dict = None,        # table profile for RealisticTable generation
    ):
        self.model_name = model_name
        self.data_type = data_type
        self.NUM_ROWS = num_rows
        self.parallelism = max(1, min(parallelism, 8))  # clamp 1–8
        self.temperature = max(0.0, min(temperature, 1.0))

        max_allowed = MAX_BATCH_SIZES.get(data_type, 100)
        if batch_size > max_allowed:
            print(
                f"[DataGenBot] WARNING: requested batch_size={batch_size} exceeds "
                f"safe limit ({max_allowed}) for '{data_type}'. "
                f"Automatically capping to {max_allowed}."
            )
            batch_size = max_allowed
        self.BATCH_SIZE = batch_size
        self.effective_batch_size = batch_size

        # ── Resolve column names: caller-supplied list takes priority ─────────
        if column_names:
            self._column_names = list(column_names)
        else:
            self._column_names = COLUMN_NAMES.get(data_type, COLUMN_NAMES["Cluster"])


        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")

        self.custom_prompt = custom_prompt.strip()
        self._profile = profile  # table profile for RealisticTable generation
        self.output_format = get_output_format(data_type)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        print(
            f"[DataGenBot] model='{model_name}' type='{data_type}' "
            f"rows={num_rows} batch={batch_size} "
            f"parallelism={self.parallelism} temp={self.temperature}"
        )

    def build_prompt(self, batch_size: int) -> str:
        # ── Realistic table: build from live profile each batch (batch_size varies) ──
        if self.data_type == "RealisticTable" and self._profile:
            return build_realistic_prompt(self._profile, batch_size)
        # ── Custom user-edited prompt (strip the batch header; we re-add it) ──
        if self.custom_prompt:
            if self.output_format == "json":
                prefix = (
                    f"Generate exactly {batch_size} UNIQUE JSON objects, formatted as a JSON array fragment.\n"
                    "Do NOT include the opening '[' or closing ']' brackets in your output."
                )
            else:
                prefix = f"Generate exactly {batch_size} UNIQUE CSV rows."
            return f"{prefix}\n\n{self.custom_prompt}"
        template = PROMPT_TEMPLATES.get(self.data_type, CLUSTER_PROMPT)
        return template.format(batch_size=batch_size)

    def clean_llm_text(self, raw_response: str) -> str:
        return "\n".join(
            line.strip() for line in raw_response.strip().splitlines()
            if line.strip() and not line.strip().startswith("```")
        )

    def parse_csv_text(self, raw_response: str) -> pd.DataFrame:
        cleaned = self.clean_llm_text(raw_response)
        return pd.read_csv(
            io.StringIO(cleaned),
            header=None,
            names=self._column_names,
        )

    def parse_json_objects(self, raw_response: str, expected_count: int) -> list:
        cleaned = self.clean_llm_text(raw_response)
        if cleaned.startswith("["):
            cleaned = cleaned[1:].strip()
        if cleaned.endswith("]"):
            cleaned = cleaned[:-1].strip()
        cleaned = cleaned.rstrip(",").strip()

        if not cleaned:
            raise ValueError("LLM returned an empty JSON fragment")

        payload = json.loads(f"[{cleaned}]")
        if not isinstance(payload, list):
            raise ValueError("Expected a list of JSON objects")
        if len(payload) != expected_count:
            raise ValueError(f"Expected {expected_count} JSON objects, got {len(payload)}")

        for idx, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Item {idx} is not a JSON object")
            season = item.get("season")
            vendors = item.get("vendors")
            if not isinstance(item.get("productId"), str):
                raise ValueError(f"Item {idx} is missing string field 'productId'")
            if not isinstance(season, dict):
                raise ValueError(f"Item {idx} is missing object field 'season'")
            if not isinstance(season.get("seasonYear"), str) or not isinstance(season.get("seasonName"), str):
                raise ValueError(f"Item {idx} has an invalid 'season' object")
            if not isinstance(vendors, list) or not vendors:
                raise ValueError(f"Item {idx} must contain at least one vendor")
            for vendor_idx, vendor in enumerate(vendors, start=1):
                if not isinstance(vendor, dict):
                    raise ValueError(f"Item {idx} vendor {vendor_idx} is not an object")
                required_vendor_keys = ("supplierNumber", "factoryNumber", "isActive")
                if not all(key in vendor for key in required_vendor_keys):
                    raise ValueError(f"Item {idx} vendor {vendor_idx} is missing required keys")

        return payload

    def call_llm(self, prompt: str) -> str:
        system_content = (
            "You are a synthetic data generation agent. "
            "Output ONLY raw JSON array fragment objects with no extra text, no markdown, no explanation."
            if self.output_format == "json"
            else
            "You are a synthetic data generation agent. "
            "Output ONLY raw CSV rows with no extra text, no headers, no markdown, no explanation."
        )
        max_tokens = _MAX_OUTPUT_TOKENS
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    # ── Internal: single batch execution (called from thread pool) ────────────
    def _execute_batch(self, batch_num: int, num_batches: int, current_batch_size: int) -> dict:
        """
        Execute one batch with up to 3 retry attempts.
        Returns a result dict; never raises — failures are captured in logs.
        """
        batch_logs = [f"[Batch {batch_num}/{num_batches}] Requesting {current_batch_size} records..."]
        prompt = self.build_prompt(current_batch_size)
        success = False
        data = None
        t0 = time.time()

        for attempt in range(1, 4):  # up to 3 attempts
            try:
                raw = self.call_llm(prompt)
                if self.output_format == "json":
                    data = self.parse_json_objects(raw, current_batch_size)
                    batch_logs.append(f"  ✔ Got {len(data)} JSON objects (attempt {attempt})")
                else:
                    df = self.parse_csv_text(raw)
                    expected_cols = len(self._column_names)
                    if df.shape[1] != expected_cols:
                        raise ValueError(f"Expected {expected_cols} columns, got {df.shape[1]}")
                    batch_logs.append(f"  ✔ Got {len(df)} rows (attempt {attempt})")
                    data = df
                success = True
                break
            except Exception as e:
                batch_logs.append(f"  ✖ Attempt {attempt} failed: {e}")

        elapsed = time.time() - t0
        if success:
            batch_logs.append(f"  ⏱ Completed in {elapsed:.1f}s")
        else:
            batch_logs.append(f"  ⚠ Skipping batch {batch_num} after 3 failed attempts.")

        return {
            "batch_num": batch_num,
            "success": success,
            "data": data,
            "logs": batch_logs,
            "elapsed": elapsed,
        }

    def generate_stream(self):
        """
        Generator that yields a status dict after every completed batch.
        Batches are executed concurrently (up to self.parallelism at a time).

        Status dict shape:
          {
            "batch_num":    int,   # how many batches have COMPLETED so far
            "num_batches":  int,
            "logs":         [str],
            "output_format":"csv" | "json",
            "partial_df":   DataFrame or None,
            "partial_json": list[dict] or None,
            "done":         bool,
            "final_df":     DataFrame or None,
            "final_json":   list[dict] or None,
            "elapsed_last": float,  # seconds for the most recent batch
          }
        """
        num_batches = math.ceil(self.NUM_ROWS / self.BATCH_SIZE)

        # Pre-compute per-batch sizes so threads can be submitted immediately
        batch_sizes: list[int] = []
        remaining = self.NUM_ROWS
        for _ in range(num_batches):
            bs = min(self.BATCH_SIZE, remaining)
            batch_sizes.append(bs)
            remaining -= bs

        # Slot-indexed result storage so the final concat is always in order
        all_dfs: list = [None] * num_batches
        all_json_batches: list = [None] * num_batches
        logs: list[str] = []
        completed_count = 0

        with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            future_to_batch = {
                executor.submit(self._execute_batch, b, num_batches, batch_sizes[b - 1]): b
                for b in range(1, num_batches + 1)
            }

            for future in as_completed(future_to_batch):
                result = future.result()
                b = result["batch_num"]
                completed_count += 1
                logs.extend(result["logs"])

                if result["success"]:
                    if self.output_format == "json":
                        all_json_batches[b - 1] = result["data"]
                    else:
                        all_dfs[b - 1] = result["data"]

                # Partial aggregates (preserving original batch order)
                partial_dfs = [d for d in all_dfs if d is not None]
                flat_json = [item for batch in all_json_batches if batch for item in batch]
                partial_df = pd.concat(partial_dfs, ignore_index=True) if partial_dfs else None
                partial_json = flat_json if flat_json else None

                yield {
                    "batch_num": completed_count,
                    "num_batches": num_batches,
                    "logs": list(logs),
                    "output_format": self.output_format,
                    "partial_df": partial_df,
                    "partial_json": partial_json,
                    "done": False,
                    "final_df": None,
                    "final_json": None,
                    "elapsed_last": result["elapsed"],
                }

        # ── Top-up loop: fill any shortfall caused by the LLM returning fewer rows ──
        def _current_total() -> int:
            if self.output_format == "json":
                return sum(len(b) for b in all_json_batches if b)
            return sum(len(d) for d in all_dfs if d is not None)

        shortfall = self.NUM_ROWS - _current_total()
        topup_attempt = 0
        max_topup_attempts = 10  # safety cap to avoid infinite loops

        while shortfall > 0 and topup_attempt < max_topup_attempts:
            topup_attempt += 1
            topup_size = min(shortfall, self.BATCH_SIZE)
            topup_batch_label = num_batches + topup_attempt
            logs.append(
                f"[Top-up {topup_attempt}] {shortfall} rows still missing — "
                f"requesting {topup_size} extra records..."
            )
            result = self._execute_batch(topup_batch_label, num_batches, topup_size)
            logs.extend(result["logs"])

            if result["success"]:
                if self.output_format == "json":
                    all_json_batches.append(result["data"])
                else:
                    all_dfs.append(result["data"])
                shortfall = self.NUM_ROWS - _current_total()
                logs.append(f"  ↳ Top-up succeeded. Remaining shortfall: {shortfall}")
            else:
                logs.append(
                    f"  ⚠ Top-up attempt {topup_attempt} failed after 3 retries; "
                    f"{shortfall} rows may still be missing."
                )
                break  # avoid hammering the endpoint if it keeps failing


        if shortfall > 0:
            logs.append(
                f"  ⚠ Could not reach {self.NUM_ROWS} rows after top-up; "
                f"final output will contain {_current_total()} rows."
            )

        # ── Final yield ────────────────────────────────────────────────────────
        if self.output_format == "json":
            if not any(b for b in all_json_batches if b):
                raise RuntimeError("No JSON data was generated. Check your API key, base URL, or prompt.")
            flat_all = [item for batch in all_json_batches if batch for item in batch]
            final_json = flat_all[: self.NUM_ROWS]
            final_df = None
        else:
            valid_dfs = [d for d in all_dfs if d is not None]
            if not valid_dfs:
                raise RuntimeError("No CSV data was generated. Check your API key, base URL, or prompt.")
            final_df = pd.concat(valid_dfs, ignore_index=True).head(self.NUM_ROWS)
            final_json = None

        yield {
            "batch_num": num_batches,
            "num_batches": num_batches,
            "logs": list(logs),
            "output_format": self.output_format,
            "partial_df": final_df,
            "partial_json": final_json,
            "done": True,
            "final_df": final_df,
            "final_json": final_json,
            "elapsed_last": 0.0,
        }

