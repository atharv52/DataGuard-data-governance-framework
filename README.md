# DataGuard 🛡️

A end-to-end data governance framework built entirely on free and open-source tooling. Covers all six pillars of data governance — contracts, quality, transformation, PII detection, lineage, and metadata catalog — on BigQuery Sandbox.

---

## Overview

In any data organization, data moves through dozens of systems, teams, and pipelines. Without governance:

- Nobody knows **what data exists** or what it means
- Nobody knows **who owns** a dataset or who to call when it breaks
- PII leaks into systems that shouldn't have it
- Pipelines fail silently with bad data
- Auditors ask *"who accessed this customer record?"* and nobody knows

DataGuard is a hands-on implementation of the six governance pillars that answer these questions:

| Pillar | Question | Tool |
|---|---|---|
| Data Contracts | What shape must data be in? | Pandera |
| Data Quality | Is the data trustworthy? | Great Expectations |
| Transformation Governance | How is raw data turned into analytics? | dbt Core + BigQuery |
| PII Detection | Does it contain sensitive info? | Microsoft Presidio |
| Data Lineage | Where did this data come from? | OpenLineage + Marquez |
| Metadata Catalog | What data do we have and who owns it? | Custom BQ Catalog |

---

## Architecture

```
Chicago Taxi Public Dataset (BigQuery)
          ↓
┌─────────────────────────────────────────────────┐
│  Phase 1: Pandera Contract                      │
│  → Validates schema, constraints, business rules│
│  → Fails fast if data violates contract         │
└─────────────────────────┬───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────┐
│  Phase 2: Great Expectations Quality            │
│  → Measures completeness, validity, uniqueness  │
│  → Generates Data Docs HTML report              │
└─────────────────────────┬───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────┐
│  Phase 2.5: dbt Transformations                 │
│  → stg_taxi_trips (view)  — cleaned staging     │
│  → mart_taxi_daily_summary (table) — aggregated │
│  → Built-in SQL tests + auto-documentation      │
└─────────────────────────┬───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────┐
│  Phase 3: Presidio PII Classification           │
│  → Scans columns for PII entities               │
│  → Writes governance_pii_classification to BQ   │
└─────────────────────────┬───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────┐
│  Phase 4: OpenLineage + Marquez Lineage         │
│  → Tracks every pipeline run                    │
│  → Records inputs, outputs, status, timestamps  │
│  → Visualizes lineage graph in Marquez UI       │
└─────────────────────────┬───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────┐
│  Phase 5: Governance Catalog                    │
│  → Crawls BQ schemas                            │
│  → Aggregates PII + lineage + dbt metadata      │
│  → Writes governance_catalog to BQ              │
└─────────────────────────────────────────────────┘
```

---

## Project Structure

```
DataGuard/
├── contracts/
│   └── taxi_contract.py          # Pandera data contract — schema + constraints + business rules
├── pipelines/
│   └── ingest_taxi.py            # Ingestion pipeline with contract validation
├── quality/
│   ├── expectations/
│   │   └── taxi_suite.py         # GX expectation suite — 6 quality dimensions
│   └── checkpoints/
│       └── taxi_checkpoint.py    # GX checkpoint runner + Data Docs
├── taxi_dbt/
│   └── models/
│       ├── staging/
│       │   ├── sources.yml           # dbt source declaration
│       │   ├── stg_taxi_trips.sql    # Staging model — type casting, standardization
│       │   └── staging.yml           # Column descriptions + dbt tests
│       └── marts/
│           ├── mart_taxi_daily_summary.sql  # Daily aggregated business metrics
│           └── marts.yml                    # Column descriptions + dbt tests
├── pii/
│   ├── scanner.py                # Presidio PII scanner — NER + regex detection
│   └── classifier.py             # Classification report + BQ write
├── lineage/
│   ├── emitter.py                # OpenLineage event emitter (START/COMPLETE/FAIL)
│   └── pipeline.py               # Full governed pipeline with lineage tracking
├── catalog/
│   ├── crawler.py                # BQ schema crawler + unified catalog builder
│   └── access_control.py        # Column-level access control report
├── docker-compose.yml            # Marquez + PostgreSQL + Marquez Web
├── Dockerfile.marquez            # Custom Marquez image with config baked in
├── marquez.yml                   # Marquez server config
├── requirements.txt              # Python dependencies
└── .env                          # GCP credentials (not committed)
```

---

## Dataset

Uses the **Chicago Taxi Trips** public BigQuery dataset:

```
bigquery-public-data.chicago_taxi_trips.taxi_trips
```

No download needed — already in BigQuery. Contains ~200M rows with numerical columns (fare, miles, duration), categorical columns (payment type, company), and timestamps — ideal for demonstrating all governance pillars.

---

## Tech Stack

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.9+ | Core language |
| Pandera | Latest | Data contract validation |
| Great Expectations | v1.x | Data quality checks |
| dbt Core + dbt-bigquery | Latest | SQL transformations + testing |
| Microsoft Presidio | Latest | PII detection (NER + regex) |
| spaCy en_core_web_lg | Latest | NLP model for Presidio |
| OpenLineage | Latest | Lineage event standard |
| Marquez | Latest | Lineage server + UI |
| Docker + docker-compose | Latest | Runs Marquez locally |
| Google BigQuery | Sandbox | Data warehouse |
| google-cloud-bigquery | Latest | BQ Python client |

---

## Prerequisites

- Python 3.9+
- Google Cloud account with BigQuery Sandbox (no credit card required)
- GCP Service Account with roles: `BigQuery Data Viewer`, `BigQuery Job User`, `BigQuery Data Editor`
- Docker Desktop

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/atharv52/DataGuard-data-governance-framework.git
cd DataGuard-data-governance-framework
```

**2. Create and activate virtual environment**

```bash
python -m venv dataGuard-env
# Windows
dataGuard-env\Scripts\activate
# Mac/Linux
source dataGuard-env/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

**4. Configure environment**

Create a `.env` file in the project root:

```
GOOGLE_APPLICATION_CREDENTIALS=path/to/your-sa-key.json
GCP_PROJECT_ID=your-gcp-project-id
```

**5. Create BigQuery dataset**

```
BigQuery Console → your project → + Add → Create dataset
Dataset ID: taxi_dbt | Location: US
```

**6. Start Marquez (for Phase 4)**

```bash
docker-compose up -d
```

---

## Running Each Phase

**Phase 1 — Data Contracts**
```bash
python -m pipelines.ingest_taxi
```

**Phase 2 — Data Quality**
```bash
python -m quality.checkpoints.taxi_checkpoint
```

**Phase 2.5 — dbt Transformations**
```bash
cd taxi_dbt
dbt debug       # verify connection
dbt build       # run models + tests
dbt docs generate && dbt docs serve   # browse docs + lineage
```

**Phase 3 — PII Detection**
```bash
python -m pii.classifier
```

**Phase 4 — Data Lineage**
```bash
python -m lineage.pipeline
# View lineage at http://localhost:3000
```

**Phase 5 — Metadata Catalog**
```bash
python -m catalog.crawler
python -m catalog.access_control
```

---

## Governance Tables in BigQuery

After running all phases, your `taxi_dbt` dataset contains:

| Table | Type | Description |
|---|---|---|
| `stg_taxi_trips` | View | dbt staging model — cleaned taxi records |
| `mart_taxi_daily_summary` | Table | dbt mart — daily aggregated business metrics |
| `stg_taxi_trips_validated` | Table | Contract-validated records with lineage tracking |
| `governance_pii_classification` | Table | PII scan results per column (Phase 3) |
| `governance_catalog` | Table | Unified governance metadata catalog (Phase 5) |

Query the catalog:

```sql
SELECT
    table_name,
    owner,
    layer,
    classification_label,
    pii_column_count,
    row_count,
    last_pipeline_run_status
FROM `your-project.taxi_dbt.governance_catalog`
ORDER BY layer, table_name
```

---

## Key Governance Concepts Covered

| Concept | Description |
|---|---|
| Data Contract | Formal producer-consumer agreement on data shape and rules |
| Shift-left governance | Catch problems at the source, not at the dashboard |
| Medallion Architecture | Bronze → Silver → Gold — governance between Bronze and Silver |
| 6 Quality Dimensions | Completeness, validity, uniqueness, timeliness, consistency, accuracy |
| Data Observability | ML-based dynamic anomaly detection — evolution beyond quality |
| Staging → Promote pattern | Load all rows, validate, promote only valid rows to prod |
| Transformations as code | SQL versioned, tested, documented in Git |
| Dataset-level lineage | Which datasets feed which |
| Column-level lineage | Which columns feed which |
| Impact analysis | What breaks downstream if I change this upstream table |
| Data Classification | Systematic sensitivity tiering of every data asset |
| Column-level access control | Unauthorized users see NULL for restricted columns |

---

## Cost

This project runs entirely within **BigQuery free tier**:

| Resource | Free tier | Estimated usage |
|---|---|---|
| Query processing | 1 TB/month | ~3 GB per full run |
| Storage | 10 GB/month | < 100 MB |

All other tools are free and open-source. No credit card required.

---

## Related Projects

- **[SQLens](https://github.com/atharv52/SQLens)** — LangChain + Llama + BigQuery Text-to-SQL agent. Together with DataGuard, covers both AI-native DE and production-grade governance practices.

---

## License

MIT