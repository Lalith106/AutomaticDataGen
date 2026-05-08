# Databricks notebook source
# MAGIC %pip install openai

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

from openai import OpenAI
import pandas as pd
import io
import math

class BasiChatBot():
    def __init__(self, model_name):
        self.model_name = model_name
        self.NUM_ROWS = 1000
        self.BATCH_SIZE = 100         # 100 rows per call = 10 total calls for 1000 rows (faster)
        self.OUT_CSV = "synthetic_store_data.csv"
        self.client = OpenAI(
            api_key= "dapi7ea4cfa21cac326cdb0320c9d72af0e0-2",
            base_url="https://adb-4224005571705028.8.azuredatabricks.net/serving-endpoints")

    def build_prompt(self, batch_size):
        PROMPT_TEMPLATE = f"""
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
        return PROMPT_TEMPLATE

    def parse_csv_text(self, raw_response):
        # Strip any accidental markdown code fences or leading/trailing whitespace
        cleaned = "\n".join(
            line.strip() for line in raw_response.strip().splitlines()
            if line.strip() and not line.strip().startswith("```")
        )
        return pd.read_csv(
            io.StringIO(cleaned),
            header=None,
            names=["STORE_NO", "DEPT_NO", "CSTD_GRADE", "PHASE_STARTDATE"]
        )

    def chatCompletionsAPI(self, prompt):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are a synthetic data generation agent. Output ONLY raw CSV rows with no extra text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    def generate_batches(self):
        all_dfs = []
        num_batches = math.ceil(self.NUM_ROWS / self.BATCH_SIZE)
        collected = 0

        for batch_num in range(1, num_batches + 1):
            remaining = self.NUM_ROWS - collected
            current_batch_size = min(self.BATCH_SIZE, remaining)

            print(f"[Batch {batch_num}/{num_batches}] Requesting {current_batch_size} rows...")

            prompt = self.build_prompt(current_batch_size)

            # Retry once on parse failure
            for attempt in range(1, 3):
                try:
                    raw_response = self.chatCompletionsAPI(prompt)
                    batch_df = self.parse_csv_text(raw_response)
                    # Basic validation: must have exactly 4 columns
                    if batch_df.shape[1] != 4:
                        raise ValueError(f"Expected 4 columns, got {batch_df.shape[1]}")
                    print(f"  ✔ Got {len(batch_df)} rows (attempt {attempt})")
                    all_dfs.append(batch_df)
                    collected += len(batch_df)
                    break
                except Exception as e:
                    print(f"  ✖ Attempt {attempt} failed: {e}")
                    if attempt == 2:
                        print(f"  Skipping batch {batch_num} after 2 failed attempts.")

            if collected >= self.NUM_ROWS:
                break

        # Combine all batches
        final_df = pd.concat(all_dfs, ignore_index=True)


        return final_df


# COMMAND ----------

obj = BasiChatBot(model_name="databricks-claude-sonnet-4-5")

final_df = obj.generate_batches()

print(final_df)
print(f"\nTotal rows generated: {len(final_df)}")

# Save to CSV
final_df.to_csv(obj.OUT_CSV, index=False)
print(f"✔ Saved to {obj.OUT_CSV}")
