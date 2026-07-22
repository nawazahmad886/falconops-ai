"""
FalconOps AI - Agent Evaluation Framework
Runs YAML-defined test sets (question + expectations) against real FalconOps AI agents,
records the resulting trajectory (tool calls + final answer), scores it against the
expectations, and persists both — enabling trend/regression tracking over time, the
"Continuous Internal Evaluation" concept (trajectory collection -> independent scoring
-> score analysis/regression).

Scoring combines cheap deterministic checks (were the expected tools actually called?
does the summary mention required keywords? is confidence high enough?) with one
LLM-as-judge call that reuses ai_monitoring_service.quality_agent's exact prompt
pattern (imported, not duplicated) — the same scorer already used for live exchange
guardrails, now applied to test-set trajectories too.

Test sets live in backend/eval/agent_test_sets/*.yaml, each a list of cases:
  - question: str
  - target: "ask" | "security_agent:<agent_id>"
  - expected:
      must_mention: [keyword, ...]      # optional
      min_confidence: 0.0-1.0           # optional
      expected_tools: [tool_name, ...]  # optional
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..core.database import db
from . import intelligence_agents_service
from . import security_agents_service
from .ai_monitoring_service import quality_agent

logger = logging.getLogger(__name__)

TEST_SET_DIR = Path(__file__).resolve().parents[2] / "eval" / "agent_test_sets"


def list_test_sets() -> List[str]:
    if not TEST_SET_DIR.exists():
        return []
    return sorted(p.stem for p in TEST_SET_DIR.glob("*.yaml"))


def _load_test_set(name: str) -> List[Dict[str, Any]]:
    path = TEST_SET_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Test set '{name}' not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return data if isinstance(data, list) else (data.get("cases") or [])


async def _dispatch(question: str, target: str) -> Dict[str, Any]:
    """Run one question through the named target agent, returning its raw result dict
    (both targets already return the same {summary, confidence, tool_trace,
    recommended_actions, ...} shape — see intelligence_agents_service._normalize_result
    / security_agents_service.run_security_agent)."""
    if target == "ask":
        return await intelligence_agents_service.ask(question, mode="auto")
    if target.startswith("security_agent:"):
        agent_id = target.split(":", 1)[1]
        result = await security_agents_service.run_security_agent(agent_id, question)
        return result or {"summary": "", "confidence": 0, "tool_trace": [], "recommended_actions": []}
    raise ValueError(f"Unknown eval target '{target}'")


def _score_deterministic(trajectory: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    summary_lower = (trajectory.get("final_summary") or "").lower()

    must_mention = expected.get("must_mention") or []
    if must_mention:
        checks["must_mention"] = all(kw.lower() in summary_lower for kw in must_mention)

    min_conf = expected.get("min_confidence")
    if min_conf is not None:
        checks["min_confidence"] = (trajectory.get("confidence") or 0) >= min_conf

    expected_tools = set(expected.get("expected_tools") or [])
    if expected_tools:
        called_tools = {t.get("tool") for t in trajectory.get("tool_calls", [])}
        checks["expected_tools"] = expected_tools.issubset(called_tools)

    passed = all(checks.values()) if checks else True
    return {"checks": checks, "deterministic_pass": passed}


async def run_test_set(test_set_name: str) -> Dict[str, Any]:
    """Run every question in a test set, capturing a trajectory + score for each, and
    persist both. Returns the run summary (trajectories/scores are looked up separately
    via get_run_history for the frontend, to keep this response small)."""
    cases = _load_test_set(test_set_name)
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)

    results: List[Dict[str, Any]] = []
    for case in cases:
        question = case["question"]
        target = case.get("target", "ask")
        expected = case.get("expected", {})

        t0 = time.monotonic()
        try:
            result = await _dispatch(question, target)
            error = None
        except Exception as e:
            logger.warning(f"Eval case failed for '{question[:80]}': {e}")
            result = {}
            error = str(e)
        duration_ms = round((time.monotonic() - t0) * 1000, 1)

        trajectory = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "test_set": test_set_name,
            "question": question,
            "target": target,
            "tool_calls": result.get("tool_trace", []),
            "final_summary": result.get("summary", ""),
            "confidence": result.get("confidence"),
            "duration_ms": duration_ms,
            "error": error,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.agent_eval_trajectories.insert_one({**trajectory})
        trajectory.pop("_id", None)

        det_score = _score_deterministic(trajectory, expected)
        quality = await quality_agent(user_input=question, ai_output=trajectory["final_summary"])
        quality_score = quality.get("quality_score")

        score_doc = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "trajectory_id": trajectory["id"],
            "test_set": test_set_name,
            "question": question,
            **det_score,
            "quality_score": quality_score,
            "quality_issues": quality.get("issues", []),
            "overall_pass": det_score["deterministic_pass"] and (quality_score or 0) >= 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.agent_eval_scores.insert_one({**score_doc})
        score_doc.pop("_id", None)

        results.append({"trajectory": trajectory, "score": score_doc})

    passed = sum(1 for r in results if r["score"]["overall_pass"])
    now_iso = datetime.now(timezone.utc).isoformat()
    run_doc = {
        "run_id": run_id,
        "test_set": test_set_name,
        "total_cases": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
        "created_at": now_iso,
    }
    await db.agent_eval_runs.insert_one({**run_doc})
    run_doc.pop("_id", None)
    return {**run_doc, "results": results}


async def get_run_history(test_set: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    query = {"test_set": test_set} if test_set else {}
    return await db.agent_eval_runs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


async def compare_to_baseline(run_id: str, baseline_run_id: str) -> Dict[str, Any]:
    """Real per-question score diff between two runs of the same test set — flags
    regressions (quality dropped, or a previously-passing question now fails) rather
    than fabricating a trend."""
    current = await db.agent_eval_scores.find({"run_id": run_id}, {"_id": 0}).to_list(500)
    baseline = await db.agent_eval_scores.find({"run_id": baseline_run_id}, {"_id": 0}).to_list(500)
    baseline_by_q = {s["question"]: s for s in baseline}

    comparisons: List[Dict[str, Any]] = []
    regressions: List[Dict[str, Any]] = []
    for s in current:
        b = baseline_by_q.get(s["question"])
        if not b:
            continue
        delta = (s.get("quality_score") or 0) - (b.get("quality_score") or 0)
        entry = {
            "question": s["question"],
            "baseline_quality_score": b.get("quality_score"),
            "current_quality_score": s.get("quality_score"),
            "delta": delta,
            "regressed": delta < 0 or (bool(b.get("overall_pass")) and not s.get("overall_pass")),
        }
        comparisons.append(entry)
        if entry["regressed"]:
            regressions.append(entry)

    return {
        "run_id": run_id, "baseline_run_id": baseline_run_id,
        "comparisons": comparisons, "regressions": regressions,
        "regression_count": len(regressions),
    }
