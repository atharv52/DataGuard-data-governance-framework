import os
import uuid
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

from lineage.emitter import LineageEmitter, make_bq_dataset
from contracts.taxi_contract import taxi_contract
import pandera as pa

load_dotenv()
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ID       = os.getenv("GCP_PROJECT_ID")


def run_pipeline():
    """
    Full governed pipeline with lineage tracking.

    Lineage graph this produces:
    bigquery-public-data.chicago_taxi_trips.taxi_trips
                        ↓  [job: taxi_ingestion]
               taxi_dbt.stg_taxi_trips_validated
    """

    emitter = LineageEmitter()
    client  = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)

    # ── Define dataset references for lineage ──────────────────────────
    source_dataset = make_bq_dataset(
        project="bigquery-public-data",
        dataset="chicago_taxi_trips",
        table="taxi_trips",
        fields=[
            ("unique_key",            "STRING"),
            ("trip_start_timestamp",  "TIMESTAMP"),
            ("trip_end_timestamp",    "TIMESTAMP"),
            ("trip_seconds",          "FLOAT"),
            ("trip_miles",            "FLOAT"),
            ("fare",                  "FLOAT"),
            ("tips",                  "FLOAT"),
            ("trip_total",            "FLOAT"),
            ("payment_type",          "STRING"),
            ("company",               "STRING"),
        ]
    )

    target_dataset = make_bq_dataset(
        project=PROJECT_ID,
        dataset="taxi_dbt",
        table="stg_taxi_trips_validated",
        fields=[
            ("unique_key",            "STRING"),
            ("trip_start_timestamp",  "TIMESTAMP"),
            ("fare",                  "FLOAT"),
            ("payment_type",          "STRING"),
            ("company",               "STRING"),
        ]
    )

    job_name = "taxi_ingestion_with_contracts"
    run_id   = str(uuid.uuid4())

    # ── Step 1: Emit START ─────────────────────────────────────────────
    print("\n── Step 1: Emitting lineage START event")
    emitter.emit_start(
        job_name=job_name,
        run_id=run_id,
        inputs=[source_dataset],
        outputs=[target_dataset],
        description="Ingests Chicago taxi trips, validates against contract, writes to BQ"
    )

    try:
        # ── Step 2: Extract ───────────────────────────────────────────
        print("\n── Step 2: Extracting from BigQuery")
        query = """
            SELECT
                unique_key,
                trip_start_timestamp,
                trip_end_timestamp,
                trip_seconds,
                trip_miles,
                fare,
                tips,
                trip_total,
                payment_type,
                company
            FROM `bigquery-public-data.chicago_taxi_trips.taxi_trips`
            WHERE trip_start_timestamp >= '2024-01-01'
              AND trip_start_timestamp <  '2024-02-01'
            LIMIT 5000
        """
        df = client.query(query).to_dataframe()
        print(f"   Fetched {len(df)} rows")

        # ── Step 3: Validate contract ──────────────────────────────────
        print("\n── Step 3: Validating against data contract")
        try:
            validated_df = taxi_contract.validate(df, lazy=True)
            print("   ✅ Contract passed")
        except pa.errors.SchemaErrors as e:
            print(f"   ⚠️  Contract warnings: {len(e.failure_cases)} issues found")
            print(e.failure_cases[["column", "check", "failure_case"]].head(5).to_string())
            validated_df = df   # continue with original in this demo

        # ── Step 4: Load to BigQuery ───────────────────────────────────
        print("\n── Step 4: Loading to BigQuery")
        table_ref  = f"{PROJECT_ID}.taxi_dbt.stg_taxi_trips_validated"
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        load_job = client.load_table_from_dataframe(
            validated_df, table_ref, job_config=job_config
        )
        load_job.result()
        print(f"   ✅ Loaded {len(validated_df)} rows to {table_ref}")

        # ── Step 5: Emit COMPLETE ──────────────────────────────────────
        print("\n── Step 5: Emitting lineage COMPLETE event")
        emitter.emit_complete(
            job_name=job_name,
            run_id=run_id,
            inputs=[source_dataset],
            outputs=[target_dataset]
        )

    except Exception as e:
        # ── Emit FAIL on any error ─────────────────────────────────────
        print(f"\n── Pipeline FAILED: {e}")
        emitter.emit_fail(
            job_name=job_name,
            run_id=run_id,
            inputs=[source_dataset],
            outputs=[target_dataset],
            error=str(e)
        )
        raise

    print("\n✅ Pipeline complete. View lineage at http://localhost:3000")


if __name__ == "__main__":
    run_pipeline()