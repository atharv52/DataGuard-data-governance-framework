import uuid
import requests
from datetime import datetime, timezone


MARQUEZ_URL = "http://localhost:5000"
NAMESPACE   = "dataGuard"


class LineageEmitter:

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _emit(self, payload: dict):
        r = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=payload
        )
        if r.status_code not in (200, 201):
            print(f"  ⚠️  Lineage emit failed: {r.status_code} {r.text}")
        return r.status_code

    def emit_start(self, job_name: str, run_id: str, inputs: list, outputs: list, description: str = ""):
        status = self._emit({
            "eventType": "START",
            "eventTime": self._now(),
            "run": {"runId": run_id},
            "job": {
                "namespace": NAMESPACE,
                "name": job_name,
                "facets": {
                    "documentation": {
                        "_producer": "dataGuard",
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json",
                        "description": description
                    }
                }
            },
            "inputs":  inputs,
            "outputs": outputs,
            "producer": "dataGuard/lineage/emitter.py"
        })
        print(f"  📡 Lineage START emitted → job: {job_name} | status: {status}")

    def emit_complete(self, job_name: str, run_id: str, inputs: list, outputs: list):
        status = self._emit({
            "eventType": "COMPLETE",
            "eventTime": self._now(),
            "run": {"runId": run_id},
            "job": {"namespace": NAMESPACE, "name": job_name},
            "inputs":  inputs,
            "outputs": outputs,
            "producer": "dataGuard/lineage/emitter.py"
        })
        print(f"  ✅ Lineage COMPLETE emitted → job: {job_name} | status: {status}")

    def emit_fail(self, job_name: str, run_id: str, inputs: list, outputs: list, error: str = ""):
        status = self._emit({
            "eventType": "FAIL",
            "eventTime": self._now(),
            "run": {"runId": run_id},
            "job": {"namespace": NAMESPACE, "name": job_name},
            "inputs":  inputs,
            "outputs": outputs,
            "producer": "dataGuard/lineage/emitter.py"
        })
        print(f"  ❌ Lineage FAIL emitted → job: {job_name} | status: {status}")


def make_bq_dataset(project: str, dataset: str, table: str, fields: list = None) -> dict:
    facets = {}
    if fields:
        facets["schema"] = {
            "_producer": "dataGuard",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
            "fields": [{"name": f[0], "type": f[1]} for f in fields]
        }
    return {
        "namespace": f"bigquery://{project}",
        "name": f"{dataset}.{table}",
        "facets": facets
    }