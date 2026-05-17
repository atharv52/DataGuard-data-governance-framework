import os
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv
import pandera as pa

from contracts.taxi_contract import taxi_contract

load_dotenv()

CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ID       = os.getenv("GCP_PROJECT_ID")

# ── 1. Pull sample from BigQuery ──────────────────────────────────────
def fetch_sample() -> pd.DataFrame:
    client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)

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
    WHERE trip_start_timestamp >= '2023-01-01'
    LIMIT 5000
"""
    print("Fetching sample from BigQuery...")
    return client.query(query).to_dataframe()


# ── 2. Validate against contract ──────────────────────────────────────
def validate(df: pd.DataFrame) -> pd.DataFrame:
    print(f"Validating {len(df)} rows against ChicagoTaxiTripsContract_v1...")
    try:
        validated_df = taxi_contract.validate(df, lazy=True)
        print("✅ Contract validation passed.")
        return validated_df

    except pa.errors.SchemaErrors as e:
        print("\n❌ Contract validation FAILED. Error report:\n")
        print(e.failure_cases.to_string(index=False))
        raise   # stop the pipeline — don't write bad data


# ── 3. Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df      = fetch_sample()
    valid_df = validate(df)

    # inspect what passed
    print(f"\nSample of validated data ({len(valid_df)} rows):")
    print(valid_df.head(3).to_string())