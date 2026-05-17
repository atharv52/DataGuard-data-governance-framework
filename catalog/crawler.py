import os
import json
import requests
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ID       = os.getenv("GCP_PROJECT_ID")
MARQUEZ_URL      = "http://localhost:5000"
DATASET_ID       = "taxi_dbt"

# ── dbt model metadata ─────────────────────────────────────────────────
# In production this comes from dbt artifacts (manifest.json)
# For this project we define it manually matching our dbt models
DBT_MODEL_METADATA = {
    "stg_taxi_trips": {
        "owner":       "Data Engineering",
        "layer":       "staging",
        "description": "Cleaned and standardized taxi trip records",
        "domain":      "Transportation",
    },
    "mart_taxi_daily_summary": {
        "owner":       "Data Engineering",
        "layer":       "marts",
        "description": "Daily aggregated taxi metrics by company and payment type",
        "domain":      "Transportation",
    },
    "stg_taxi_trips_validated": {
        "owner":       "Data Engineering",
        "layer":       "staging",
        "description": "Contract-validated taxi trip records with lineage tracking",
        "domain":      "Transportation",
    },
    "governance_pii_classification": {
        "owner":       "Data Governance",
        "layer":       "governance",
        "description": "PII classification report for all scanned tables",
        "domain":      "Governance",
    }
}


def crawl_bq_tables(client: bigquery.Client) -> list:
    """
    Crawls all tables in the taxi_dbt dataset.
    Returns list of table metadata dicts.
    """
    print(f"Crawling BigQuery dataset: {PROJECT_ID}.{DATASET_ID}")
    tables     = client.list_tables(f"{PROJECT_ID}.{DATASET_ID}")
    table_list = []

    for table_ref in tables:
        table = client.get_table(table_ref)
        columns = [
            {"name": f.name, "type": f.field_type, "nullable": f.is_nullable}
            for f in table.schema
        ]
        table_list.append({
            "table_name":    table.table_id,
            "full_table_id": f"{PROJECT_ID}.{DATASET_ID}.{table.table_id}",
            "table_type":    table.table_type,
            "row_count":     table.num_rows,
            "size_bytes":    table.num_bytes,
            "created_at":    table.created.isoformat() if table.created else None,
            "modified_at":   table.modified.isoformat() if table.modified else None,
            "columns":       columns,
            "column_count":  len(columns),
        })
        print(f"  ✅ Crawled: {table.table_id} ({table.num_rows} rows, {len(columns)} columns)")

    return table_list


def fetch_pii_classification(client: bigquery.Client) -> dict:
    """
    Reads PII classification results from Phase 3.
    Returns dict of table_name → max classification tier.
    """
    print("\nFetching PII classification from governance table...")
    try:
        query = f"""
            SELECT
                table_name,
                MAX(classification_tier)  AS max_tier,
                MAX(classification_label) AS max_label,
                COUNTIF(pii_detected)     AS pii_column_count
            FROM `{PROJECT_ID}.{DATASET_ID}.governance_pii_classification`
            GROUP BY table_name
        """
        df = client.query(query).to_dataframe()
        result = {}
        for _, row in df.iterrows():
            result[row["table_name"]] = {
                "max_classification_tier":  int(row["max_tier"]),
                "max_classification_label": row["max_label"],
                "pii_column_count":         int(row["pii_column_count"]),
            }
        print(f"  ✅ Found classification for {len(result)} tables")
        return result
    except Exception as e:
        print(f"  ⚠️  Could not fetch PII classification: {e}")
        return {}


def fetch_lineage_status(table_name: str) -> dict:
    """
    Queries Marquez API for last pipeline run status for a given output table.
    """
    try:
        # get all jobs in dataGuard namespace
        r = requests.get(
            f"{MARQUEZ_URL}/api/v1/jobs",
            params={"namespace": "dataGuard", "limit": 100}
        )
        if r.status_code != 200:
            return {"last_run_status": "UNKNOWN", "last_run_at": None}

        jobs = r.json().get("jobs", [])
        for job in jobs:
            # check if this job writes to our table
            outputs = job.get("latestRun", {}).get("outputDatasetVersions", [])
            for output in outputs:
                if table_name in output.get("datasetName", ""):
                    latest_run = job.get("latestRun", {})
                    return {
                        "last_run_status": latest_run.get("state", "UNKNOWN"),
                        "last_run_at":     latest_run.get("endAt", None),
                        "lineage_job":     job.get("name", ""),
                    }
        return {"last_run_status": "NO_LINEAGE", "last_run_at": None, "lineage_job": ""}
    except Exception:
        return {"last_run_status": "UNKNOWN", "last_run_at": None, "lineage_job": ""}


def build_catalog(table_list: list, pii_map: dict) -> pd.DataFrame:
    """
    Combines all metadata sources into a unified catalog DataFrame.
    """
    print("\nBuilding unified governance catalog...")
    rows = []

    for table in table_list:
        name    = table["table_name"]
        dbt_meta = DBT_MODEL_METADATA.get(name, {
            "owner":       "Unknown",
            "layer":       "unknown",
            "description": "",
            "domain":      "Unknown"
        })
        pii_meta     = pii_map.get(name, {
            "max_classification_tier":  1,
            "max_classification_label": "PUBLIC",
            "pii_column_count":         0,
        })
        lineage_meta = fetch_lineage_status(name)

        rows.append({
            # ── Identity ───────────────────────────────────────────────
            "table_name":               name,
            "full_table_id":            table["full_table_id"],
            "table_type":               table["table_type"],

            # ── Business metadata ──────────────────────────────────────
            "owner":                    dbt_meta["owner"],
            "domain":                   dbt_meta["domain"],
            "layer":                    dbt_meta["layer"],
            "description":              dbt_meta["description"],

            # ── Technical metadata ─────────────────────────────────────
            "row_count":                table["row_count"],
            "column_count":             table["column_count"],
            "size_bytes":               table["size_bytes"],
            "created_at":               table["created_at"],
            "modified_at":              table["modified_at"],

            # ── Sensitivity metadata (from Phase 3) ────────────────────
            "classification_tier":      pii_meta["max_classification_tier"],
            "classification_label":     pii_meta["max_classification_label"],
            "pii_column_count":         pii_meta["pii_column_count"],

            # ── Lineage metadata (from Phase 4) ────────────────────────
            "last_pipeline_run_status": lineage_meta["last_run_status"],
            "last_pipeline_run_at":     lineage_meta["last_run_at"],
            "lineage_job":              lineage_meta.get("lineage_job", ""),

            # ── Catalog metadata ───────────────────────────────────────
            "catalog_updated_at":       datetime.now(timezone.utc).replace(tzinfo=None),
        })

    return pd.DataFrame(rows)


def write_catalog(catalog_df: pd.DataFrame, client: bigquery.Client):
    """
    Writes the unified catalog to BigQuery.
    """
    table_ref  = f"{PROJECT_ID}.{DATASET_ID}.governance_catalog"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("table_name",               "STRING"),
            bigquery.SchemaField("full_table_id",            "STRING"),
            bigquery.SchemaField("table_type",               "STRING"),
            bigquery.SchemaField("owner",                    "STRING"),
            bigquery.SchemaField("domain",                   "STRING"),
            bigquery.SchemaField("layer",                    "STRING"),
            bigquery.SchemaField("description",              "STRING"),
            bigquery.SchemaField("row_count",                "INTEGER"),
            bigquery.SchemaField("column_count",             "INTEGER"),
            bigquery.SchemaField("size_bytes",               "INTEGER"),
            bigquery.SchemaField("created_at",               "STRING"),
            bigquery.SchemaField("modified_at",              "STRING"),
            bigquery.SchemaField("classification_tier",      "INTEGER"),
            bigquery.SchemaField("classification_label",     "STRING"),
            bigquery.SchemaField("pii_column_count",         "INTEGER"),
            bigquery.SchemaField("last_pipeline_run_status", "STRING"),
            bigquery.SchemaField("last_pipeline_run_at",     "STRING"),
            bigquery.SchemaField("lineage_job",              "STRING"),
            bigquery.SchemaField("catalog_updated_at",       "TIMESTAMP"),
        ]
    )

    job = client.load_table_from_dataframe(
        catalog_df, table_ref, job_config=job_config
    )
    job.result()
    print(f"\n✅ Catalog written to {table_ref}")


def print_catalog(catalog_df: pd.DataFrame):
    print("\n" + "="*70)
    print("  GOVERNANCE CATALOG")
    print("="*70)
    for _, row in catalog_df.iterrows():
        print(f"\n  📋 Table         : {row['table_name']}")
        print(f"     Full ID       : {row['full_table_id']}")
        print(f"     Owner         : {row['owner']}")
        print(f"     Domain        : {row['domain']}")
        print(f"     Layer         : {row['layer']}")
        print(f"     Description   : {row['description']}")
        print(f"     Rows          : {row['row_count']}")
        print(f"     Columns       : {row['column_count']}")
        print(f"     Classification: {row['classification_label']} (Tier {row['classification_tier']})")
        print(f"     PII Columns   : {row['pii_column_count']}")
        print(f"     Last Run      : {row['last_pipeline_run_status']}")
        print(f"     Lineage Job   : {row['lineage_job']}")
    print("\n" + "="*70)


if __name__ == "__main__":
    client     = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
    table_list = crawl_bq_tables(client)
    pii_map    = fetch_pii_classification(client)
    catalog_df = build_catalog(table_list, pii_map)
    print_catalog(catalog_df)
    write_catalog(catalog_df, client)