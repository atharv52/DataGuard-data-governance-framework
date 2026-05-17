import pandas as pd
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from typing import Dict, List
from dataclasses import dataclass, field

# ── PII entity types Presidio can detect ──────────────────────────────
ENTITIES_TO_DETECT = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "LOCATION",
    "DATE_TIME",
    "IP_ADDRESS",
    "URL",
    "US_BANK_NUMBER",
    "MEDICAL_LICENSE",
]

# ── Classification tier mapping ────────────────────────────────────────
# Maps detected entity types to sensitivity tiers
ENTITY_TIER_MAP = {
    "PERSON":           4,   # PII
    "EMAIL_ADDRESS":    4,   # PII
    "PHONE_NUMBER":     4,   # PII
    "US_SSN":           5,   # Sensitive PII
    "CREDIT_CARD":      5,   # Sensitive PII
    "US_BANK_NUMBER":   5,   # Sensitive PII
    "MEDICAL_LICENSE":  5,   # Sensitive PII
    "LOCATION":         3,   # Confidential
    "IP_ADDRESS":       3,   # Confidential
    "DATE_TIME":        2,   # Internal
    "URL":              2,   # Internal
}

TIER_LABELS = {
    1: "PUBLIC",
    2: "INTERNAL",
    3: "CONFIDENTIAL",
    4: "PII",
    5: "SENSITIVE_PII"
}


@dataclass
class ColumnScanResult:
    column_name:        str
    sample_size:        int
    pii_detected:       bool
    detected_entities:  List[str]       = field(default_factory=list)
    max_confidence:     float           = 0.0
    classification_tier: int            = 1
    classification_label: str          = "PUBLIC"
    sample_hits:        int             = 0


class PIIScanner:
    def __init__(self):
        print("Initializing Presidio analyzer...")
        self.analyzer  = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        print("✅ Presidio ready.")

    def scan_column(
        self,
        column_name: str,
        values: List[str],
        sample_size: int = 100
    ) -> ColumnScanResult:
        """
        Scans a sample of values from one column for PII.
        Returns a ColumnScanResult with classification metadata.
        """
        # take a sample to keep scanning fast
        sample = [str(v) for v in values if v is not None][:sample_size]

        detected_entities = []
        max_confidence    = 0.0
        hits              = 0

        for value in sample:
            if not value.strip():
                continue

            results = self.analyzer.analyze(
                text=value,
                entities=ENTITIES_TO_DETECT,
                language="en"
            )

            if results:
                hits += 1
                for result in results:
                    detected_entities.append(result.entity_type)
                    max_confidence = max(max_confidence, result.score)

        # deduplicate entity types
        detected_entities = list(set(detected_entities))

        # determine classification tier
        tier = 1   # default PUBLIC
        for entity in detected_entities:
            entity_tier = ENTITY_TIER_MAP.get(entity, 1)
            tier = max(tier, entity_tier)

        pii_detected = tier >= 4

        return ColumnScanResult(
            column_name=column_name,
            sample_size=len(sample),
            pii_detected=pii_detected,
            detected_entities=detected_entities,
            max_confidence=round(max_confidence, 3),
            classification_tier=tier,
            classification_label=TIER_LABELS[tier],
            sample_hits=hits
        )

    def scan_dataframe(self, df: pd.DataFrame) -> List[ColumnScanResult]:
        """
        Scans all string/object columns in a DataFrame for PII.
        Skips numeric and timestamp columns.
        """
        results = []
        # only scan text columns — no point scanning floats/timestamps
        text_columns = df.select_dtypes(include=["object", "string"]).columns

        print(f"\nScanning {len(text_columns)} text columns for PII...\n")

        for col in text_columns:
            values = df[col].dropna().tolist()
            print(f"  Scanning: {col} ({len(values)} values)...")
            result = self.scan_column(col, values)
            results.append(result)
            status = "🔴 PII" if result.pii_detected else f"🟢 {result.classification_label}"
            print(f"  └─ {status} | entities: {result.detected_entities or 'none'} | confidence: {result.max_confidence}")

        return results