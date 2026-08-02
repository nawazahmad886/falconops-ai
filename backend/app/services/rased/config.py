"""
RASED runtime configuration.

Execution safety is enforced here, not just documented: EXECUTION_MODE defaults
to "simulated" and there is exactly one path to "live" — the RASED_EXECUTION_MODE
environment variable must be set to the literal string "live". No code path in
this subsystem branches to a live adapter based on anything other than this one
value, and every ActionResult records the execution_mode it ran under, so the
audit trail stays self-describing regardless of how this module is configured
at deploy time.
"""
import os

from ...models.rased_schemas import ExecutionMode, Source

EXECUTION_MODE: ExecutionMode = (
    "live" if os.environ.get("RASED_EXECUTION_MODE", "").strip().lower() == "live" else "simulated"
)

# Mongo collections holding seeded synthetic data. One raw collection per
# adapter source, plus the curated alert and evidence catalogs the generator
# produces alongside them.
ALERTS_COLLECTION = "rased_synthetic_alerts"
EVIDENCE_COLLECTION = "rased_synthetic_evidence"

SOURCE_COLLECTIONS: dict[Source, str] = {
    "elk": "rased_synthetic_elk",
    "appdynamics": "rased_synthetic_appdynamics",
    "solarwinds": "rased_synthetic_solarwinds",
    "mq": "rased_synthetic_mq",
    "db": "rased_synthetic_db",
    "cmdb": "rased_synthetic_cmdb",
    "changes": "rased_synthetic_changes",
}

DEFAULT_SEED = 42

# BM25 is the default: zero external services, and the demo must never
# depend on a vector store being provisioned. "vector" is a config-selected
# optional upgrade behind the same SOPRetriever interface.
SOP_RETRIEVER_BACKEND = os.environ.get("RASED_SOP_RETRIEVER_BACKEND", "bm25").strip().lower()

# When set, every RASED LLM call (see llm.py) returns a cached response with
# a small fixed delay instead of calling a real provider, so a slow or
# rate-limited model never ruins a live demo run.
DEMO_MODE = os.environ.get("RASED_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")
