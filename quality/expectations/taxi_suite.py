import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite

def build_taxi_suite():
    context = gx.get_context()
    suite_name = "chicago_taxi_quality_suite"

    suite = ExpectationSuite(name=suite_name)

    # ── Completeness ──────────────────────────────────────────────────
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="unique_key"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="trip_start_timestamp"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="fare", mostly=0.80))

    # ── Validity ──────────────────────────────────────────────────────
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="fare", min_value=0, max_value=10000, mostly=0.99))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="trip_miles", min_value=0, max_value=500, mostly=0.99))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="trip_seconds", min_value=0, max_value=86400, mostly=0.99))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeInSet(
        column="payment_type",
        value_set=["Cash", "Credit Card", "Mobile", "No Charge", "Unknown", "Prcard", "Dispute"],
        mostly=0.99
    ))

    # ── Uniqueness ────────────────────────────────────────────────────
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="unique_key"))

    # ── Row count (timeliness proxy) ──────────────────────────────────
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=100, max_value=100000))

    # ── Statistical drift ─────────────────────────────────────────────
    suite.add_expectation(gx.expectations.ExpectColumnMeanToBeBetween(column="fare", min_value=3.0, max_value=100.0))

    try:
        context.suites.add(suite)
    except Exception:
        context.suites.update(suite)

    print(f"✅ Suite '{suite_name}' saved with {len(suite.expectations)} expectations.")
    return suite


if __name__ == "__main__":
    build_taxi_suite()