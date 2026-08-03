"""
Live-scenario demo/test for the Agentic AI Workflow Diagnoser.

run_diagnoser() has two real, load-bearing external dependencies:
intelligence_agents_service.incident_analysis() (itself 7 parallel tool
calls + one LLM call + a Mongo write) and one more direct LLM call for
ranked-hypothesis synthesis. If either the LLM provider or the underlying
telemetry backend isn't actually configured/reachable in a given
environment, run_diagnoser() degrades or errors for reasons that have
nothing to do with its own ranking/formatting logic.

This test isolates that logic: it mocks incident_analysis(),
find_similar_incidents(), and chat_completion() with one consistent,
realistic incident scenario (evidence that plausibly-but-wrongly points at
a database, with the real cause being a downstream payment-gateway
dependency — same "revision-worthy" evidence shape used elsewhere in this
codebase), then runs the REAL run_diagnoser() against it and prints a
formatted executive RCA report.

Run with: pytest -s -v backend/tests/test_agentic_diagnoser_demo.py
(-s is required to see the printed report; pytest captures stdout by default)
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import app.services.agentic_trace_service as agentic_trace_service_module
from app.services.agentic_workflow_service import run_diagnoser

# ---------------------------------------------------------------------------
# One consistent, realistic incident scenario. Evidence is deliberately built
# so a competent RCA ranks "payment-gateway dependency failure" above
# "database contention" — the DB signal is real but a downstream symptom.
# ---------------------------------------------------------------------------

MOCK_EVIDENCE_DOC = {
    "summary": (
        "checkout-api error rate elevated to 12.4% over the last 15 minutes; "
        "invoice-db connection-pool utilization also elevated to 91%."
    ),
    "evidence": [
        "checkout-api 5xx rate: 12.4% (baseline 0.3%)",
        "invoice-db connection pool utilization: 91% (baseline 45%)",
        "18 slow-query warnings logged on invoice-db in the last 5 minutes",
        "AppDynamics exit-span failure rate checkout-api -> payment-gateway: 34% (baseline 1.2%)",
        "payment-gateway exit-span degradation began ~6 minutes before invoice-db pool saturation",
        "No deployment recorded for checkout-api, invoice-db, or payment-gateway in the last 60 minutes",
    ],
    "confidence": 0.55,
    "tool_trace": [
        {"tool": "get_metrics", "params": {"service": "checkout-api"}, "summary": "elevated 5xx rate", "count": 1},
        {"tool": "get_logs", "params": {"service": "invoice-db"}, "summary": "slow-query warnings", "count": 18},
        {"tool": "get_deployments", "params": {"service": "checkout-api"}, "summary": "no recent deploys", "count": 0},
    ],
}

MOCK_SIMILAR_INCIDENTS = [
    {
        "text": (
            "2026-05-14: checkout-api elevated errors traced to a payment-gateway timeout storm; "
            "invoice-db pool saturation was a downstream symptom. Resolved by failing over payment-gateway."
        ),
        "similarity": 0.88,
    },
    {
        "text": "2026-02-02: invoice-db slow queries caused by a missing index after a schema migration.",
        "similarity": 0.61,
    },
]

MOCK_LLM_HYPOTHESES = {
    "hypotheses": [
        {
            "root_cause": (
                "The payment-gateway dependency is failing intermittently; checkout-api's synchronous "
                "calls to it are backing up connections into invoice-db, which is a downstream symptom, "
                "not the root cause."
            ),
            "confidence": 0.82,
            "category": "infra",
            "evidence": [
                "Exit-span failure rate to payment-gateway at 34% vs 1.2% baseline",
                "Gateway degradation preceded DB pool saturation by ~6 minutes",
                "No deployment correlates with the incident window, ruling out a bad release",
            ],
        },
        {
            "root_cause": "Database connection-pool exhaustion on invoice-db is the primary cause of checkout-api errors.",
            "confidence": 0.35,
            "category": "infra",
            "evidence": [
                "invoice-db connection pool at 91% utilization",
                "18 slow-query warnings in the preceding 5 minutes",
            ],
        },
        {
            "root_cause": "A recent code change to checkout-api introduced a regression.",
            "confidence": 0.1,
            "category": "deploy",
            "evidence": [
                "No deployment recorded in the last 60 minutes for any implicated service — weak support for this hypothesis",
            ],
        },
    ],
}


def _mock_trace_db() -> MagicMock:
    """agentic_trace_service.py imports `db` by name at module load
    (`from ..core.database import db`), so patching app.core.database.db
    would NOT affect its already-bound local reference — must patch the
    name on agentic_trace_service_module itself."""
    seq_counter = {"n": 0}

    async def _find_one_and_update(*_args, **_kwargs):
        seq_counter["n"] += 1
        return {"seq": seq_counter["n"]}

    mock_db = MagicMock()
    mock_db.agentic_trace_counters.find_one_and_update = AsyncMock(side_effect=_find_one_and_update)
    mock_db.agentic_trace.insert_one = AsyncMock(return_value=None)
    return mock_db


def _print_executive_rca_report(target: str, result: dict) -> None:
    hypotheses = result.get("hypotheses", [])
    similar = result.get("similar_past_incidents", [])

    print("\n" + "=" * 72)
    print("EXECUTIVE ROOT CAUSE ANALYSIS REPORT")
    print(f"Target: {target}")
    print(f"Generated: {result.get('queried_at')}")
    print(f"LLM: {result.get('llm_provider')}/{result.get('llm_model')}")
    print("=" * 72)

    if not hypotheses:
        print("\nNo hypothesis could be synthesized.")
        return

    top = hypotheses[0]
    print(f"\nTOP FINDING (confidence {round(top['confidence'] * 100)}%)")
    print(f"  {top['root_cause']}")
    print("\n  Supporting evidence:")
    for e in top["evidence"]:
        print(f"    - {e}")

    if len(hypotheses) > 1:
        print("\nALTERNATIVE HYPOTHESES CONSIDERED")
        for h in hypotheses[1:]:
            print(f"  #{h['rank']} ({round(h['confidence'] * 100)}%) {h['root_cause']}")

    if similar:
        print("\nSIMILAR PAST INCIDENTS")
        for s in similar:
            print(f"  - (similarity {round(s['similarity'] * 100)}%) {s['text'][:140]}")

    print("=" * 72 + "\n")


class TestDiagnoserFullScenarioDemo:
    def test_full_scenario_produces_executive_ready_rca(self):
        mock_trace_db = _mock_trace_db()

        with patch(
            "app.services.agentic_workflow_service.intelligence_agents_service.incident_analysis",
            AsyncMock(return_value=MOCK_EVIDENCE_DOC),
        ), patch(
            "app.services.agentic_workflow_service.rag_service.find_similar_incidents",
            AsyncMock(return_value=MOCK_SIMILAR_INCIDENTS),
        ), patch(
            "app.services.agentic_workflow_service.chat_completion",
            AsyncMock(return_value={
                "provider": "demo", "model": "demo-mock",
                "response": json.dumps(MOCK_LLM_HYPOTHESES),
            }),
        ), patch.object(agentic_trace_service_module, "db", mock_trace_db):
            result = asyncio.run(run_diagnoser("checkout-api", hours=1))

        _print_executive_rca_report("checkout-api", result)

        # Real assertions, not just a printout — this is what "proper RCA
        # came out" means in code: correctly ranked, cited, non-fabricated.
        hypotheses = result["hypotheses"]
        assert len(hypotheses) == 3
        assert hypotheses[0]["rank"] == 1
        assert "payment-gateway" in hypotheses[0]["root_cause"].lower()
        assert hypotheses[0]["confidence"] > hypotheses[1]["confidence"] > hypotheses[2]["confidence"]
        assert all(h["evidence"] for h in hypotheses), "every hypothesis must cite evidence"
        assert result["similar_past_incidents"] == MOCK_SIMILAR_INCIDENTS
        assert result["run_id"], "run_id must be present for trace correlation"

    def test_llm_returning_no_valid_json_falls_back_honestly(self):
        """If the LLM call fails to produce parseable hypotheses, run_diagnoser
        must fall back to the single-answer summary rather than fabricate a
        ranked list — this is the behavior an executive report depends on
        being trustworthy even in the worst case."""
        mock_trace_db = _mock_trace_db()

        with patch(
            "app.services.agentic_workflow_service.intelligence_agents_service.incident_analysis",
            AsyncMock(return_value=MOCK_EVIDENCE_DOC),
        ), patch(
            "app.services.agentic_workflow_service.rag_service.find_similar_incidents",
            AsyncMock(return_value=[]),
        ), patch(
            "app.services.agentic_workflow_service.chat_completion",
            AsyncMock(return_value={"provider": "demo", "model": "demo-mock", "response": "I cannot help with that."}),
        ), patch.object(agentic_trace_service_module, "db", mock_trace_db):
            result = asyncio.run(run_diagnoser("checkout-api", hours=1))

        assert len(result["hypotheses"]) == 1
        assert result["hypotheses"][0]["root_cause"] == MOCK_EVIDENCE_DOC["summary"]

    def test_judge_rejects_uncited_hypothesis_but_keeps_cited_one(self):
        """The Judge validation step must reject any hypothesis with no
        supporting evidence, independent of how confident the LLM claimed to
        be — an uncited claim is not fit for an executive-facing report."""
        mock_trace_db = _mock_trace_db()
        llm_response = {
            "hypotheses": [
                {"root_cause": "Confident but unsupported guess.", "confidence": 0.95, "category": "infra", "evidence": []},
                {
                    "root_cause": "Payment-gateway dependency failure.",
                    "confidence": 0.6, "category": "infra",
                    "evidence": ["Exit-span failure rate 34%"],
                },
            ],
        }

        with patch(
            "app.services.agentic_workflow_service.intelligence_agents_service.incident_analysis",
            AsyncMock(return_value=MOCK_EVIDENCE_DOC),
        ), patch(
            "app.services.agentic_workflow_service.rag_service.find_similar_incidents",
            AsyncMock(return_value=[]),
        ), patch(
            "app.services.agentic_workflow_service.chat_completion",
            AsyncMock(return_value={"provider": "demo", "model": "demo-mock", "response": json.dumps(llm_response)}),
        ), patch.object(agentic_trace_service_module, "db", mock_trace_db):
            result = asyncio.run(run_diagnoser("checkout-api", hours=1))

        hypotheses = result["hypotheses"]
        assert len(hypotheses) == 1, "the uncited 0.95-confidence hypothesis must be rejected regardless of its claimed confidence"
        assert hypotheses[0]["root_cause"] == "Payment-gateway dependency failure."
        assert hypotheses[0]["rank"] == 1
