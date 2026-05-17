import os
from google.cloud import bigquery
from google.cloud.bigquery import PolicyTagList
from dotenv import load_dotenv

load_dotenv()
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ID       = os.getenv("GCP_PROJECT_ID")
DATASET_ID       = "taxi_dbt"

# ── Columns classified as PII in Phase 3 ──────────────────────────────
# In production this is read dynamically from governance_pii_classification
PII_COLUMNS = {
    "stg_taxi_trips": [],             # no PII detected in taxi dataset
    "stg_taxi_trips_validated": [],   # same
}

# ── Governance report ──────────────────────────────────────────────────
# Shows what WOULD be restricted in a real PII scenario
GOVERNANCE_REPORT = [
    {
        "table":      "stg_taxi_trips",
        "column":     "company",
        "tier":       "PUBLIC",
        "action":     "NO_RESTRICTION",
        "reason":     "No PII detected"
    },
    {
        "table":      "stg_taxi_trips",
        "column":     "payment_type",
        "tier":       "PUBLIC",
        "action":     "NO_RESTRICTION",
        "reason":     "No PII detected"
    },
]


def print_access_control_report():
    """
    Prints a governance access control report.
    Shows classification and restriction status per column.
    In production, PII columns would have policy tags applied
    restricting access to authorized roles only.
    """
    print("\n" + "="*70)
    print("  ACCESS CONTROL REPORT")
    print("="*70)
    print("""
  How column-level access control works in production:
  ─────────────────────────────────────────────────────
  1. Data Catalog Policy Taxonomy is created in GCP
  2. Policy Tags are created per sensitivity tier:
       └── Sensitive PII  → only data-privacy-team@company.com
       └── PII            → only analysts@company.com
       └── Confidential   → only internal@company.com
  3. Policy Tags are applied to columns in BigQuery
  4. Users without the role see NULL for that column

  Example — if 'email' column existed:
  ─────────────────────────────────────────────────────
  SELECT email FROM stg_taxi_trips
    → Data Engineer (authorized) : john@example.com
    → Analyst (unauthorized)     : NULL
  """)

    print("  Column Classification Status:")
    print("  " + "-"*50)
    for row in GOVERNANCE_REPORT:
        tier_emoji = "🔴" if "PII" in row["tier"] else "🟢"
        print(f"  {tier_emoji} {row['table']}.{row['column']}")
        print(f"     Tier    : {row['tier']}")
        print(f"     Action  : {row['action']}")
        print(f"     Reason  : {row['reason']}")
    print("\n" + "="*70)


def demonstrate_policy_tag_structure():
    """
    Shows the BigQuery Policy Tag structure that would be created
    for a dataset containing real PII.
    """
    print("""
  Policy Tag Taxonomy Structure (production example):
  ─────────────────────────────────────────────────────
  DataGuard Taxonomy
  └── Tier 5: SENSITIVE_PII
  │     └── Applied to: SSN, credit_card, bank_account columns
  │     └── Authorized: data-privacy-team only
  │
  └── Tier 4: PII
  │     └── Applied to: name, email, phone columns
  │     └── Authorized: analysts + data-privacy-team
  │
  └── Tier 3: CONFIDENTIAL
        └── Applied to: ip_address, location columns
        └── Authorized: internal teams
    """)


if __name__ == "__main__":
    print_access_control_report()
    demonstrate_policy_tag_structure()