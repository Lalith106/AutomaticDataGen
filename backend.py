from openai import OpenAI
import pandas as pd
import io
import math
import json

# ── Default prompt templates per data type ──────────────────────────────────

CLUSTER_PROMPT = """
Generate exactly {batch_size} UNIQUE CSV rows.

Columns: STORE_NO,DEPT_NO,CSTD_GRADE,PHASE_STARTDATE

Rules:
- STORE_NO: 4-digit number, zero-padded, digits 1–9 only (e.g. 0123). Do NOT repeat STORE_NO within this batch.
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
}

OUTPUT_FORMATS = {
    "Cluster": "csv",
    "ProductVendor": "json",
}


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


class DataGenBot:
    def __init__(self, model_name: str, api_key: str, base_url: str,
                 data_type: str, num_rows: int, batch_size: int,
                 custom_prompt: str = ""):
        self.model_name = model_name
        self.data_type = data_type
        self.NUM_ROWS = num_rows
        self.BATCH_SIZE = batch_size
        api_key="dapi7ea4cfa21cac326cdb0320c9d72af0e0-2"
        base_url="https://adb-4224005571705028.8.azuredatabricks.net/serving-endpoints"
        self.custom_prompt = custom_prompt.strip()
        self.output_format = get_output_format(data_type)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        print(f"Initialized DataGenBot with model '{model_name}', data type '{data_type}', num_rows={num_rows}, batch_size={batch_size}")

    def build_prompt(self, batch_size: int) -> str:
        if self.custom_prompt:
            if self.output_format == "json":
                prefix = (
                    f"Generate exactly {batch_size} UNIQUE JSON objects, formatted as a JSON array fragment.\n"
                    "Do NOT include the opening '[' or closing ']' brackets in your output."
                )
            else:
                prefix = f"Generate exactly {batch_size} UNIQUE CSV rows."
            return f"{prefix}\n\n{self.custom_prompt}"
        # Use default template for selected data type
        template = PROMPT_TEMPLATES.get(self.data_type, CLUSTER_PROMPT)
        return template.format(batch_size=batch_size)

    def clean_llm_text(self, raw_response: str) -> str:
        return "\n".join(
            line.strip() for line in raw_response.strip().splitlines()
            if line.strip() and not line.strip().startswith("```")
        )

    def parse_csv_text(self, raw_response: str) -> pd.DataFrame:
        cleaned = self.clean_llm_text(raw_response)
        col_names = COLUMN_NAMES.get(self.data_type, COLUMN_NAMES["Cluster"])
        return pd.read_csv(
            io.StringIO(cleaned),
            header=None,
            names=col_names
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
            "You are a synthetic data generation agent. Output ONLY raw JSON array fragment objects with no extra text."
            if self.output_format == "json"
            else "You are a synthetic data generation agent. Output ONLY raw CSV rows with no extra text."
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_content
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    def generate_stream(self):
        """
        Generator that yields a status dict after every batch:
          {
            "batch_num": int,
            "num_batches": int,
            "logs": [str],
            "output_format": "csv" | "json",
            "partial_df": DataFrame or None,
            "partial_json": list[dict] or None,
            "done": bool,
            "final_df": DataFrame or None,
            "final_json": list[dict] or None,
          }
        Consume with: for status in bot.generate_stream(): ...
        """
        all_dfs = []
        all_json_objects = []
        logs = []
        num_batches = math.ceil(self.NUM_ROWS / self.BATCH_SIZE)
        collected = 0

        for batch_num in range(1, num_batches + 1):
            remaining = self.NUM_ROWS - collected
            current_batch_size = min(self.BATCH_SIZE, remaining)

            batch_logs = [f"[API Call {batch_num}/{num_batches}] Requesting {current_batch_size} records..."]
            prompt = self.build_prompt(current_batch_size)
            success = False

            for attempt in range(1, 3):
                try:
                    raw = self.call_llm(prompt)
                    if self.output_format == "json":
                        json_objects = self.parse_json_objects(raw, current_batch_size)
                        batch_logs.append(f"  ✔ Got {len(json_objects)} JSON objects (attempt {attempt})")
                        all_json_objects.extend(json_objects)
                        collected += len(json_objects)
                    else:
                        df = self.parse_csv_text(raw)
                        expected_cols = len(COLUMN_NAMES.get(self.data_type, COLUMN_NAMES["Cluster"]))
                        if df.shape[1] != expected_cols:
                            raise ValueError(f"Expected {expected_cols} columns, got {df.shape[1]}")
                        batch_logs.append(f"  ✔ Got {len(df)} rows (attempt {attempt})")
                        all_dfs.append(df)
                        collected += len(df)
                    success = True
                    break
                except Exception as e:
                    batch_logs.append(f"  ✖ Attempt {attempt} failed: {e}")

            if not success:
                batch_logs.append(f"  ⚠ Skipping API call {batch_num} after 2 failed attempts.")

            logs.extend(batch_logs)

            partial_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else None
            partial_json = list(all_json_objects) if all_json_objects else None
            yield {
                "batch_num": batch_num,
                "num_batches": num_batches,
                "logs": list(logs),
                "output_format": self.output_format,
                "partial_df": partial_df,
                "partial_json": partial_json,
                "done": False,
                "final_df": None,
                "final_json": None,
            }

            if collected >= self.NUM_ROWS:
                break

        if self.output_format == "json":
            if not all_json_objects:
                raise RuntimeError("No JSON data was generated. Check your API key, base URL, or prompt.")
            final_json = all_json_objects[:self.NUM_ROWS]
            final_df = None
        else:
            if not all_dfs:
                raise RuntimeError("No data was generated. Check your API key, base URL, or prompt.")
            final_df = pd.concat(all_dfs, ignore_index=True)
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
        }

