import pandera as pa
from pandera import Column, DataFrameSchema, Check

# ─────────────────────────────────────────────
# DATA CONTRACT: Chicago Taxi Trips
# Owner:        Data Engineering Team
# Version:      1.0.0
# Description:  Validates raw taxi trip records
#               before landing in BigQuery
# ─────────────────────────────────────────────

taxi_contract = DataFrameSchema(
    columns={
        # ── Layer 1: Schema (type + nullability) ──────────────────────

        "unique_key": Column(
            str,
            nullable=False,
            unique=True,
            description="Unique identifier for each trip"
        ),

        "trip_start_timestamp": Column(
            "datetime64[us, UTC]",
            nullable=False,
            description="Trip start time in UTC"
        ),

        "trip_end_timestamp": Column(
            "datetime64[us, UTC]",
            nullable=True,   # can be null if trip is ongoing
            description="Trip end time in UTC"
        ),

        # ── Layer 2: Constraints (value rules) ────────────────────────

        "trip_seconds": Column(
            float,
            nullable=True,
            checks=[
                Check.greater_than_or_equal_to(0),      # no negative durations
                Check.less_than_or_equal_to(86400),      # max 24 hours
            ],
            description="Trip duration in seconds"
        ),

        "trip_miles": Column(
            float,
            nullable=True,
            checks=[
                Check.greater_than_or_equal_to(0),       # no negative miles
                Check.less_than_or_equal_to(500),        # reasonable max distance
            ],
            description="Trip distance in miles"
        ),

        "fare": Column(
            float,
            nullable=True,
            checks=[
                Check.greater_than_or_equal_to(0),
            ],
            description="Fare amount in USD"
        ),

        "tips": Column(
            float,
            nullable=True,
            checks=[
                Check.greater_than_or_equal_to(0),
            ],
            description="Tip amount in USD"
        ),

        "trip_total": Column(
            float,
            nullable=True,
            checks=[
                Check.greater_than_or_equal_to(0),
            ],
            description="Total trip cost in USD"
        ),

        "payment_type": Column(
            str,
            nullable=True,
            checks=[
                # Layer 2: allowed value set
                Check.isin([
                    "Cash",
                    "Credit Card",
                    "Mobile",
                    "No Charge",
                    "Unknown",
                    "Prcard",
                    "Dispute"
                ])
            ],
            description="Method of payment"
        ),

        "company": Column(
            str,
            nullable=True,
            description="Taxi company name"
        ),
    },

    # ── Layer 3: Business Rules (cross-column) ────────────────────────
    checks=[
        # trip_total must be >= fare (tips/extras can only add, not subtract)
        Check(
            lambda df: (
                df[df["fare"].notna() & df["trip_total"].notna()]
                .pipe(lambda d: d["trip_total"] >= d["fare"])
                .all()
            ),
            error="Business rule violated: trip_total must be >= fare"
        ),

        # trip_end must be after trip_start where both exist
        Check(
            lambda df: (
                df[df["trip_start_timestamp"].notna() & df["trip_end_timestamp"].notna()]
                .pipe(lambda d: d["trip_end_timestamp"] >= d["trip_start_timestamp"])
                .all()
            ),
            error="Business rule violated: trip_end_timestamp must be >= trip_start_timestamp"
        ),
    ],

    name="ChicagoTaxiTripsContract_v1",
    strict=False,   # allow extra columns not listed above (don't fail on them)
    coerce=True,    # attempt type coercion before validation
)