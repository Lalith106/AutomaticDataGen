import google.generativeai as genai
import time
import math
import json
from tqdm import tqdm

# ----------------- YOUR API LIMITS (RPM 50) -----------------
# MIN_DELAY_SECONDS = 1.3 (to respect 50 RPM)
MIN_DELAY_SECONDS = 1.3

# ------------ CONFIG ----------------
NUM_ROWS = 100  # Total number of root objects to generate
BATCH_SIZE = 10 # Adjusted BATCH_SIZE lower due to HIGH VERBOSITY of the output
OUT_JSON = "synthetic_product_vendor_data.json"

# Replace with your actual API key
genai.configure(api_key="AIzaSyDdvxazjvmbS7bbwsA0Fs1upOnPRI99LM4") # Placeholder
model = genai.GenerativeModel("models/gemini-2.5-flash")

# 📢 MODIFIED PROMPT FOR NESTED JSON STRUCTURE
PROMPT_TEMPLATE_JSON = """
Generate exactly {n} UNIQUE JSON objects, formatted as a JSON array fragment.
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

# -----------------------------------------------------------
# Functions remain largely the same, but the token limit is raised.
# -----------------------------------------------------------

def extract_json_fragment(text):
    """Cleans up the text fragment to ensure it's suitable for joining."""
    text = text.replace("```json", "").replace("```", "").strip()
    if text.startswith('['):
        text = text[1:].strip()
    if text.endswith(']'):
        text = text[:-1].strip()

    return text

def generate_batch(n, retries=5, initial_backoff=5):
    prompt = PROMPT_TEMPLATE_JSON.format(n=n)
    backoff_time = initial_backoff

    for attempt in range(retries):
        try:
            response = model.generate_content(
                prompt,
                # Increased tokens to 8192 because nested JSON is very verbose.
                generation_config={"max_output_tokens": 8192}
            )
            return extract_json_fragment(response.text)

        except Exception as e:
            # Implements exponential backoff to handle rate limits and transient errors
            print(f"⚠ Gemini error (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"Waiting for {backoff_time} seconds before retrying...")
                time.sleep(backoff_time)
                backoff_time *= 2
            else:
                print("Max retries reached. Skipping batch.")
    return ""

def main():
    collected_fragments = []

    total_calls_required = math.ceil(NUM_ROWS / BATCH_SIZE)
    print(f"Total API Calls expected: {total_calls_required}")
    print(f"Throttle set to {MIN_DELAY_SECONDS} seconds per request to respect 50 RPM.")

    pbar = tqdm(total=total_calls_required, desc="Generating Nested JSON Batches")
    start_time = time.time()

    batches_completed = 0
    while batches_completed < total_calls_required:
        remaining_rows = NUM_ROWS - (batches_completed * BATCH_SIZE)
        current_batch_size = min(BATCH_SIZE, remaining_rows)

        batch_fragment = generate_batch(current_batch_size)

        # Enforce the 1.3 second delay to respect 50 RPM
        time.sleep(MIN_DELAY_SECONDS)

        if not batch_fragment:
            print("\nAPI returned no data. Stopping.")
            break

        collected_fragments.append(batch_fragment)
        batches_completed += 1
        pbar.update(1)

    pbar.close()

    if collected_fragments:
        clean_fragments = [f for f in collected_fragments if f.strip()]

        # Stitch all fragments together into one valid JSON array
        final_json_string = "[\n" + ",\n".join(clean_fragments) + "\n]"

        try:
            with open(OUT_JSON, 'w') as f:
                f.write(final_json_string)

            # Load and validate the JSON to print a sample
            final_data = json.loads(final_json_string)
            print("\n--- Generation Complete ---")
            print(f"Saved: {OUT_JSON} containing {len(final_data)} JSON objects.")
            print(f"Total time elapsed: {time.time() - start_time:.2f} seconds")
            print("\nFirst 2 JSON objects:")
            print(json.dumps(final_data[:2], indent=2))

        except json.JSONDecodeError as e:
            print(f"\nFATAL ERROR: Failed to decode the generated JSON. Check the output file {OUT_JSON}")
            print(f"Decoding Error: {e}")

    else:
        print("No data collected.")

if __name__ == "__main__":
    main()
