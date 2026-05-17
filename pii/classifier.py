import os
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from dotenv import load_dotenv

from pii.scanner import PIIScanner, ColumnScanResult, TIER_LABELS
from typing import List

load_dotenv()
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ID       = os.getenv("GCP_PROJECT_ID")


def fetch_sample() -> pd.DataFrame:
    client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
    # use our dbt staging table — already clean
    query = f"""
        SELECT
            unique_key,
            payment_type,
            company
        FROM `{PROJECT_ID}.taxi_dbt.stg_taxi_trips`
        LIMIT 500
    """
    print("Fetching sample from stg_taxi_trips...")
    return client.query(query).to_dataframe()


def build_classification_report(
    results: List[ColumnScanResult],
    table_name: str
) -> pd.DataFrame:
    """
    Converts scan results into a structured classification report DataFrame.
    This will be written to BigQuery as a governance metadata table.
    """
    rows = []
    for r in results:
        rows.append({
            "table_name":             table_name,
            "column_name":            r.column_name,
            "classification_tier":    r.classification_tier,
            "classification_label":   r.classification_label,
            "pii_detected":           r.pii_detected,
            "detected_entities":      ", ".join(r.detected_entities) if r.detected_entities else "none",
            "max_confidence_score":   r.max_confidence,
            "sample_size":            r.sample_size,
            "sample_hits":            r.sample_hits,
            "scanned_at":             datetime.now(timezone.utc).replace(tzinfo=None),
        })
    return pd.DataFrame(rows)


def write_to_bigquery(report_df: pd.DataFrame):
    """
    Writes classification report to a governance metadata table in BigQuery.
    This feeds into the Phase 5 data catalog.
    """
    client    = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
    table_ref = f"{PROJECT_ID}.taxi_dbt.governance_pii_classification"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("table_name",           "STRING"),
            bigquery.SchemaField("column_name",          "STRING"),
            bigquery.SchemaField("classification_tier",  "INTEGER"),
            bigquery.SchemaField("classification_label", "STRING"),
            bigquery.SchemaField("pii_detected",         "BOOLEAN"),
            bigquery.SchemaField("detected_entities",    "STRING"),
            bigquery.SchemaField("max_confidence_score", "FLOAT"),
            bigquery.SchemaField("sample_size",          "INTEGER"),
            bigquery.SchemaField("sample_hits",          "INTEGER"),
            bigquery.SchemaField("scanned_at",           "TIMESTAMP"),
        ]
    )

    job = client.load_table_from_dataframe(
        report_df, table_ref, job_config=job_config
    )
    job.result()
    print(f"\n✅ Classification report written to {table_ref}")


def print_report(report_df: pd.DataFrame):
    print("\n" + "="*60)
    print("  PII CLASSIFICATION REPORT")
    print("="*60)
    for _, row in report_df.iterrows():
        tier_emoji = "🔴" if row["pii_detected"] else "🟢"
        print(f"\n  {tier_emoji} Column        : {row['column_name']}")
        print(f"     Classification : {row['classification_label']} (Tier {row['classification_tier']})")
        print(f"     Entities found : {row['detected_entities']}")
        print(f"     Confidence     : {row['max_confidence_score']}")
        print(f"     Hits / Sample  : {row['sample_hits']} / {row['sample_size']}")
    print("\n" + "="*60)


if __name__ == "__main__":
    # 1. fetch sample
    df = fetch_sample()

    # 2. scan for PII
    scanner = PIIScanner()
    results = scanner.scan_dataframe(df)

    # 3. build report
    report_df = build_classification_report(results, table_name="stg_taxi_trips")

    # 4. print to terminal
    print_report(report_df)

    # 5. write to BQ governance table
    write_to_bigquery(report_df)