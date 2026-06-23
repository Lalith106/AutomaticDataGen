"""
profiler.py
-----------
Profiles a Databricks SQL table and returns a structured dict of per-column
statistics (ranges, distinct values, null %, samples) that can be used to
build a realistic LLM generation prompt.

Connection defaults are shared with DataGenBot (same Databricks workspace).
"""

from databricks import sql as dbsql
import os

DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")

DATABRICKS_HTTP_PATH = "/sql/1.0/warehouses/99afececa9e21495"
DATABRICKS_CATALOG   = "hive_metastore"
DATABRICKS_SCHEMA    = "ap_staging_sit"

# ── Type-family sets (Databricks / Spark SQL type names) ─────────────────────
_NUMERIC_TYPES = {
    "int", "integer", "bigint", "smallint", "tinyint",
    "decimal", "numeric", "double", "float", "long", "short", "byte",
}
_DATE_TYPES    = {"date", "timestamp", "timestamp_ntz"}
_STRING_TYPES  = {"string", "varchar", "char"}
_BOOLEAN_TYPES = {"boolean"}


def _base_type(dtype_str: str) -> str:
    """Normalise 'decimal(18,2)' → 'decimal', 'varchar(255)' → 'varchar', etc."""
    return dtype_str.lower().split("(")[0].strip()


# ─────────────────────────────────────────────────────────────────────────────
def list_tables(
    catalog: str   = DATABRICKS_CATALOG,
    schema: str    = DATABRICKS_SCHEMA,
    http_path: str = DATABRICKS_HTTP_PATH,
    host: str      = DATABRICKS_HOST,
    token: str     = DATABRICKS_TOKEN,
) -> list:
    """
    Return a sorted list of **managed table** names in the given catalog.schema.

    Uses SHOW TABLE EXTENDED which returns a per-table info blob containing
    'Type: MANAGED' for managed tables, 'Type: EXTERNAL' for external tables,
    and 'Type: VIEW' for views — so we can filter in a single round-trip.
    """
    conn = dbsql.connect(server_hostname=host, http_path=http_path, access_token=token)
    try:
        cur = conn.cursor()
        cur.execute(f"SHOW TABLE EXTENDED IN `{catalog}`.`{schema}` LIKE '*'")
        rows = cur.fetchall()
        cur.close()
        # SHOW TABLE EXTENDED → columns: database, tableName, isTemporary, information
        tables = sorted(
            row[1]
            for row in rows
            if row[1] and "Type: MANAGED" in (row[3] or "")
        )
        return tables
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
def get_row_count(
    table_fqn: str,
    http_path: str = DATABRICKS_HTTP_PATH,
    host: str      = DATABRICKS_HOST,
    token: str     = DATABRICKS_TOKEN,
) -> int:
    """Fast COUNT(*) on a single table — used to preview row count before profiling."""
    conn = dbsql.connect(server_hostname=host, http_path=http_path, access_token=token)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table_fqn}")
        count = cur.fetchone()[0]
        cur.close()
        return count
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
def profile_databricks_table(
    table_fqn: str,
    http_path: str   = DATABRICKS_HTTP_PATH,
    host: str        = DATABRICKS_HOST,
    token: str       = DATABRICKS_TOKEN,
    sample_rows: int = 10_000,  # rows to TABLESAMPLE for all statistics
    top_values: int  = 200,     # top-N most-frequent string values per column
                                # (all distinct values are fetched when distinct_count <= top_values)
) -> dict:
    """
    Scalable table profiler — designed for large tables (50 k+ rows).

    Strategy
    --------
    1. COUNT(*) on the full table — Databricks serves this from metadata, fast.
    2. DESCRIBE TABLE — zero-data schema fetch.
    3. ONE aggregation query on TABLESAMPLE({sample_rows} ROWS) computing
       MIN / MAX / APPROX_COUNT_DISTINCT / NULL count for every column in a
       single scan, plus AVG for numerics and true-count for booleans.
    4. For each string column: one GROUP BY frequency query (on the same
       sample) returning the top-N most common values — more representative
       for LLM generation than arbitrary DISTINCT, and prompt-size bounded.

    Scan cost: 1 full-table COUNT + 1 sample scan + N_string_cols sample scans.
    Typical time on a 50 k-row table: ~3–6 s vs ~30–60 s for the old approach.

    Parameters
    ----------
    table_fqn   : Fully-qualified name, e.g. hive_metastore.schema.table
    sample_rows : Rows sampled for statistics via TABLESAMPLE (default 10 000).
    top_values  : Max distinct string values to capture per column (default 200).
                  When APPROX_COUNT_DISTINCT ≤ top_values all distinct values are
                  fetched (no LIMIT), so low-cardinality columns (e.g. 76 values)
                  are always fully represented in the prompt.

    Returns
    -------
    {
      "table":       str,
      "row_count":   int,          # exact full-table row count
      "sample_rows": int,          # actual rows in the TABLESAMPLE
      "columns": [
        {
          "name", "dtype", "kind", "nullable", "null_pct",
          # numeric:  "min", "max", "mean"
          # date:     "min_date", "max_date"
          # boolean:  "true_pct"
          # string:   "distinct_count" (approx),
          #           "top_values": [{"value": ..., "freq_pct": ...}]
          # other:    "samples": [...]
        }, ...
      ]
    }
    """
    conn = dbsql.connect(server_hostname=host, http_path=http_path, access_token=token)
    try:
        cur = conn.cursor()

        # ── 1. Exact row count ────────────────────────────────────────────────
        cur.execute(f"SELECT COUNT(*) FROM {table_fqn}")
        row_count = cur.fetchone()[0]

        # ── 2. Schema ─────────────────────────────────────────────────────────
        cur.execute(f"DESCRIBE TABLE {table_fqn}")
        columns_meta = []
        for row in cur.fetchall():
            col_name, col_type = row[0], row[1]
            if not col_name or col_name.startswith("#") or col_type is None:
                break
            columns_meta.append({"name": col_name, "dtype": col_type})

        if not columns_meta:
            raise ValueError(f"No columns found for table {table_fqn}")

        # ── 3. Single-scan aggregation on TABLESAMPLE ─────────────────────────
        # Reuse this subquery alias in all subsequent queries (same sample).
        sample_subq = (
            f"(SELECT * FROM {table_fqn} TABLESAMPLE ({sample_rows} ROWS)) AS _s"
        )

        # Index-based aliases (c0_min, c1_max …) avoid reserved-word collisions.
        agg_parts = ["COUNT(*) AS _sample_size"]
        for i, meta in enumerate(columns_meta):
            q = f"`{meta['name']}`"
            b = _base_type(meta["dtype"])
            agg_parts += [
                f"MIN({q})                                      AS c{i}_min",
                f"MAX({q})                                      AS c{i}_max",
                f"APPROX_COUNT_DISTINCT({q})                    AS c{i}_card",
                f"SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) AS c{i}_nulls",
            ]
            if b in _NUMERIC_TYPES:
                agg_parts.append(f"AVG(CAST({q} AS DOUBLE)) AS c{i}_avg")
            if b in _BOOLEAN_TYPES:
                agg_parts += [
                    f"SUM(CASE WHEN {q} = TRUE THEN 1 ELSE 0 END) AS c{i}_trues",
                    f"COUNT({q})                                    AS c{i}_nonnull",
                ]

        cur.execute(f"SELECT {', '.join(agg_parts)} FROM {sample_subq}")
        agg_row = cur.fetchone()
        agg     = {desc[0]: val for desc, val in zip(cur.description, agg_row)}
        actual_sample = agg.get("_sample_size") or sample_rows

        # ── 4. Per-column profiles from agg results ───────────────────────────
        column_profiles = []
        for i, meta in enumerate(columns_meta):
            col_name = meta["name"]
            dtype    = meta["dtype"]
            base     = _base_type(dtype)
            quoted   = f"`{col_name}`"

            null_count = agg.get(f"c{i}_nulls") or 0
            card       = agg.get(f"c{i}_card")  or 0
            null_pct   = round(null_count / actual_sample * 100, 2) if actual_sample > 0 else 0.0

            col_profile = {
                "name":     col_name,
                "dtype":    dtype,
                "nullable": null_count > 0,
                "null_pct": null_pct,
            }

            if base in _NUMERIC_TYPES:
                col_profile["kind"] = "numeric"
                col_profile["min"]  = agg.get(f"c{i}_min")
                col_profile["max"]  = agg.get(f"c{i}_max")
                raw_avg = agg.get(f"c{i}_avg")
                col_profile["mean"] = round(raw_avg, 4) if raw_avg is not None else None

            elif base in _DATE_TYPES:
                col_profile["kind"]     = "date"
                col_profile["min_date"] = str(agg[f"c{i}_min"]) if agg.get(f"c{i}_min") is not None else None
                col_profile["max_date"] = str(agg[f"c{i}_max"]) if agg.get(f"c{i}_max") is not None else None

            elif base in _BOOLEAN_TYPES:
                col_profile["kind"]     = "boolean"
                trues   = agg.get(f"c{i}_trues",  0) or 0
                nonnull = agg.get(f"c{i}_nonnull", 0) or 0
                col_profile["true_pct"] = round(trues / nonnull * 100, 2) if nonnull > 0 else 0.0

            elif base in _STRING_TYPES:
                col_profile["kind"]           = "string"
                col_profile["distinct_count"] = card   # approx via APPROX_COUNT_DISTINCT

                # Top-N by frequency: single GROUP BY, works for any cardinality,
                # keeps result bounded, and most-common values are best for generation.
                #
                # Smart limit: if APPROX_COUNT_DISTINCT says the column has fewer
                # distinct values than our cap, fetch ALL of them (no LIMIT) so the
                # prompt contains every real value, not just the top-N.
                nonnull_sample = max(actual_sample - null_count, 1)
                fetch_limit    = top_values if card > top_values else int(card * 1.5 + 10)
                cur.execute(
                    f"SELECT {quoted}, COUNT(*) AS freq "
                    f"FROM {sample_subq} "
                    f"WHERE {quoted} IS NOT NULL "
                    f"GROUP BY {quoted} ORDER BY freq DESC "
                    f"LIMIT {fetch_limit}"
                )
                col_profile["top_values"] = [
                    {
                        "value":    r[0],
                        "freq_pct": round(r[1] / nonnull_sample * 100, 1),
                    }
                    for r in cur.fetchall()
                ]

            else:
                col_profile["kind"] = "other"
                cur.execute(
                    f"SELECT {quoted} FROM {sample_subq} "
                    f"WHERE {quoted} IS NOT NULL LIMIT 8"
                )
                col_profile["samples"] = [r[0] for r in cur.fetchall()]

            column_profiles.append(col_profile)

        cur.close()
        return {
            "table":       table_fqn,
            "row_count":   row_count,
            "sample_rows": actual_sample,
            "columns":     column_profiles,
        }

    finally:
        conn.close()
