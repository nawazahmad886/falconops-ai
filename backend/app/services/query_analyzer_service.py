"""
FalconOps AI - Query Analyzer Service
Analyzes database queries for performance issues and provides optimization suggestions
"""
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from ..core.database import db

logger = logging.getLogger(__name__)


# ======================== QUERY ANALYSIS RULES ========================

ANALYSIS_RULES = [
    {
        "id": "select_star",
        "pattern": r"SELECT\s+\*",
        "severity": "warning",
        "title": "Avoid SELECT *",
        "suggestion": "Specify only the columns you need to reduce I/O and network overhead",
        "category": "performance",
    },
    {
        "id": "no_where",
        "pattern": r"^(SELECT|UPDATE|DELETE)\s+.*(?!.*WHERE)",
        "severity": "high",
        "title": "Missing WHERE clause",
        "suggestion": "Add a WHERE clause to avoid full table scans. This query will process every row.",
        "category": "performance",
    },
    {
        "id": "no_index_hint",
        "pattern": r"WHERE\s+\w+\s+LIKE\s+'%",
        "severity": "warning",
        "title": "Leading wildcard in LIKE",
        "suggestion": "Leading wildcard (LIKE '%...') prevents index usage. Consider full-text search instead.",
        "category": "indexing",
    },
    {
        "id": "cartesian_join",
        "pattern": r"JOIN\s+\w+\s*(?!.*ON)",
        "severity": "critical",
        "title": "JOIN without ON condition",
        "suggestion": "This may produce a Cartesian product. Always specify JOIN conditions.",
        "category": "performance",
    },
    {
        "id": "subquery_in_select",
        "pattern": r"SELECT\s+.*\(\s*SELECT",
        "severity": "warning",
        "title": "Subquery in SELECT",
        "suggestion": "Correlated subqueries in SELECT run once per row. Consider using a JOIN instead.",
        "category": "performance",
    },
    {
        "id": "order_no_limit",
        "pattern": r"ORDER\s+BY\s+.*(?!.*LIMIT)",
        "severity": "info",
        "title": "ORDER BY without LIMIT",
        "suggestion": "Sorting large result sets without LIMIT is expensive. Add LIMIT if you only need top N rows.",
        "category": "performance",
    },
    {
        "id": "multiple_or",
        "pattern": r"(OR\s+\w+\s*=\s*){3,}",
        "severity": "info",
        "title": "Multiple OR conditions",
        "suggestion": "Replace multiple OR conditions with IN() for better readability and potential performance gains.",
        "category": "optimization",
    },
    {
        "id": "not_in",
        "pattern": r"NOT\s+IN\s*\(",
        "severity": "info",
        "title": "NOT IN usage",
        "suggestion": "NOT IN can behave unexpectedly with NULLs. Consider NOT EXISTS or LEFT JOIN WHERE IS NULL.",
        "category": "correctness",
    },
    {
        "id": "implicit_conversion",
        "pattern": r"WHERE\s+\w+\s*=\s*'?\d+'?",
        "severity": "info",
        "title": "Potential type mismatch",
        "suggestion": "Ensure the compared value matches the column type to avoid implicit conversions that bypass indexes.",
        "category": "indexing",
    },
    {
        "id": "insert_no_columns",
        "pattern": r"INSERT\s+INTO\s+\w+\s+VALUES",
        "severity": "warning",
        "title": "INSERT without column list",
        "suggestion": "Specify column names in INSERT for clarity and to avoid breakage when schema changes.",
        "category": "correctness",
    },
]


def analyze_query(query: str) -> Dict:
    """Analyze a single SQL query and return findings"""
    query_upper = query.strip().upper()
    findings = []

    for rule in ANALYSIS_RULES:
        try:
            if re.search(rule["pattern"], query_upper, re.IGNORECASE | re.DOTALL):
                findings.append({
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "suggestion": rule["suggestion"],
                    "category": rule["category"],
                })
        except re.error:
            pass

    # Special check: no WHERE on UPDATE/DELETE
    if re.match(r"^\s*(UPDATE|DELETE)\s+", query_upper) and "WHERE" not in query_upper:
        findings.append({
            "rule_id": "dangerous_no_where",
            "severity": "critical",
            "title": "UPDATE/DELETE without WHERE",
            "suggestion": "This will affect ALL rows in the table. Always add a WHERE clause.",
            "category": "safety",
        })

    # Fingerprint
    fingerprint = _fingerprint_query(query)

    # Score (0-100, lower is better)
    score = 100
    for f in findings:
        if f["severity"] == "critical":
            score -= 30
        elif f["severity"] == "high":
            score -= 20
        elif f["severity"] == "warning":
            score -= 10
        elif f["severity"] == "info":
            score -= 5
    score = max(score, 0)

    return {
        "query": query[:500],
        "fingerprint": fingerprint,
        "score": score,
        "quality": "excellent" if score >= 90 else "good" if score >= 70 else "needs_improvement" if score >= 50 else "poor",
        "findings": findings,
        "finding_count": len(findings),
    }


def _fingerprint_query(query: str) -> str:
    """Generate a normalized fingerprint for query dedup"""
    fp = re.sub(r"'[^']*'", "'?'", query)
    fp = re.sub(r"\b\d+\b", "?", fp)
    fp = re.sub(r"\s+", " ", fp).strip().upper()
    return fp[:200]


async def analyze_and_store(query: str, db_id: str = "", duration_ms: float = 0) -> Dict:
    """Analyze a query and store the result"""
    result = analyze_query(query)
    result["id"] = str(uuid.uuid4())
    result["db_id"] = db_id
    result["duration_ms"] = duration_ms
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    await db.query_analyses.insert_one(result)
    result.pop("_id", None)
    return result


async def get_slow_queries(db_id: str = None, hours: int = 24, limit: int = 50) -> List[Dict]:
    """Get analyzed slow queries"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query = {"analyzed_at": {"$gte": cutoff}}
    if db_id:
        query["db_id"] = db_id
    return await db.query_analyses.find(query, {"_id": 0}).sort("duration_ms", -1).limit(limit).to_list(limit)


async def get_query_stats(hours: int = 24) -> Dict:
    """Get query analysis statistics"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    total = await db.query_analyses.count_documents({"analyzed_at": {"$gte": cutoff}})

    quality_pipeline = [
        {"$match": {"analyzed_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$quality", "count": {"$sum": 1}}},
    ]
    by_quality = await db.query_analyses.aggregate(quality_pipeline).to_list(10)

    category_pipeline = [
        {"$match": {"analyzed_at": {"$gte": cutoff}}},
        {"$unwind": "$findings"},
        {"$group": {"_id": "$findings.category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_category = await db.query_analyses.aggregate(category_pipeline).to_list(10)

    return {
        "total_analyzed": total,
        "by_quality": [{"quality": q["_id"], "count": q["count"]} for q in by_quality],
        "by_finding_category": [{"category": c["_id"], "count": c["count"]} for c in by_category],
    }
