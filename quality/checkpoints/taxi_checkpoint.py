import os
import pandas as pd
import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


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


def run_quality_check():
    context = gx.get_context()
    df      = fetch_sample()

    # ── 1. Build suite ─────────────────────────────────────────────────
    suite = ExpectationSuite(name="chicago_taxi_quality_suite")

    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="unique_key"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="trip_start_timestamp"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="fare", mostly=0.80))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="fare", min_value=0, max_value=10000, mostly=0.99))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="trip_miles", min_value=0, max_value=500, mostly=0.99))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="trip_seconds", min_value=0, max_value=86400, mostly=0.99))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeInSet(
        column="payment_type",
        value_set=["Cash", "Credit Card", "Mobile", "No Charge", "Unknown", "Prcard", "Dispute"],
        mostly=0.99
    ))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="unique_key"))
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=100, max_value=100000))
    suite.add_expectation(gx.expectations.ExpectColumnMeanToBeBetween(column="fare", min_value=3.0, max_value=100.0))

    try:
        context.suites.add(suite)
    except Exception:
        context.suites.update(suite)

    # ── 2. Datasource + batch — all in same context ────────────────────
    datasource = context.data_sources.add_pandas(name="taxi_datasource")
    asset      = datasource.add_dataframe_asset(name="taxi_sample")
    batch_def  = asset.add_batch_definition_whole_dataframe("taxi_batch")

    # ── 3. Validation definition ───────────────────────────────────────
    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="taxi_validation",
            data=batch_def,
            suite=suite
        )
    )

    # ── 4. Run ─────────────────────────────────────────────────────────
    results = validation_def.run(batch_parameters={"dataframe": df})

    # ── 5. Print summary ───────────────────────────────────────────────
    print(f"\n{'✅ PASSED' if results.success else '❌ FAILED'} — Quality Check Results")
    for result in results.results:
        status = "✅" if result.success else "❌"
        col    = result.expectation_config.kwargs.get("column", "table-level")
        etype  = result.expectation_config.type
        print(f"  {status} {etype} → {col}")

    return results


if __name__ == "__main__":
    run_quality_check()