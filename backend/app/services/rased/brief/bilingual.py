"""
Bilingual (Arabic/English) executive brief, built once per investigation
from already-computed state — deterministic Python templates, not an LLM
call. A translation an operator can't verify at 3am, feeding an approval
decision, is the wrong place to trust an unverified model output, and this
build has no way to test real LLM Arabic-translation quality end-to-end (no
live provider access while authoring it). So the brief is built the same
computed-facts-in-Python way ImpactAgent's sentence is, just without an LLM
writing step at all — every field is templated directly from
InvestigationState.

Five fixed fields, per the plan: what is happening, who is affected and how
many, probable cause and confidence, what RASED already did, what it needs
from a human.
"""
from typing import Dict, List, Optional

from ....models.rased_schemas import Hypothesis, InvestigationState


def _top_hypothesis(state: InvestigationState) -> Optional[Hypothesis]:
    surviving = [h for h in state.hypotheses if not h.superseded]
    if not surviving:
        return None
    return max(surviving, key=lambda h: h.confidence)


def _what_rased_did_en(state: InvestigationState) -> str:
    if not state.action_results:
        return "No actions have been executed yet."
    parts = [f"a {r.execution_mode}-mode action that {'succeeded' if r.success else 'failed'}" for r in state.action_results]
    return "RASED already ran " + "; ".join(parts) + "."


def _what_rased_did_ar(state: InvestigationState) -> str:
    if not state.action_results:
        return "لم يتم تنفيذ أي إجراء حتى الآن."
    parts = [f"إجراء بوضع {r.execution_mode} {'نجح' if r.success else 'فشل'}" for r in state.action_results]
    return "قامت RASED بالفعل بتنفيذ: " + "، ".join(parts) + "."


def _needed_from_human_en(state: InvestigationState) -> str:
    if state.status == "awaiting_approval":
        return "Approval is required before RASED executes a DESTRUCTIVE-tier action. Please review and approve or reject."
    if state.status == "escalated":
        return "This investigation was escalated for human review — confidence, blast radius, or policy required it."
    if state.status == "suppressed":
        return "No action needed — this event was automatically suppressed (duplicate, storm, or maintenance window)."
    return "No human action is required at this time."


def _needed_from_human_ar(state: InvestigationState) -> str:
    if state.status == "awaiting_approval":
        return 'يلزم الحصول على موافقة قبل أن تنفذ RASED إجراءً من فئة "مدمر". يرجى المراجعة والموافقة أو الرفض.'
    if state.status == "escalated":
        return "تم تصعيد هذا التحقيق للمراجعة البشرية — بسبب مستوى الثقة أو نطاق التأثير أو السياسة المعتمدة."
    if state.status == "suppressed":
        return "لا حاجة لأي إجراء — تم كبح هذا الحدث تلقائيًا (حدث مكرر، عاصفة تنبيهات، أو نافذة صيانة)."
    return "لا يلزم أي إجراء بشري في الوقت الحالي."


def build_bilingual_brief(state: InvestigationState) -> Dict[str, Dict[str, str]]:
    affected_service = state.alerts[0].service if state.alerts else "unknown service"
    alert_count = len(state.alerts)
    impact = state.business_impact
    hypothesis = _top_hypothesis(state)

    en = {
        "what_is_happening": f"{affected_service} is experiencing {state.root_signature or 'an unclassified issue'}.",
        "who_and_how_many": (
            f"{affected_service} is affected, with {alert_count} alert(s) correlated to this incident"
            + (f"; an estimated {impact.transactions_at_risk} transactions are at risk." if impact else ".")
        ),
        "probable_cause_and_confidence": (
            f"{hypothesis.statement} (confidence {hypothesis.confidence:.0%})"
            if hypothesis else "No root-cause hypothesis has been established yet."
        ),
        "what_rased_did": _what_rased_did_en(state),
        "needs_from_human": _needed_from_human_en(state),
    }

    ar = {
        "what_is_happening": f"تعاني الخدمة {affected_service} من المشكلة التالية: {state.root_signature or 'مشكلة غير مصنفة'}.",
        "who_and_how_many": (
            f"الخدمة المتأثرة هي {affected_service}، وعدد التنبيهات المرتبطة بهذا الحادث هو {alert_count}"
            + (f"؛ تشير التقديرات إلى أن {impact.transactions_at_risk} معاملة معرضة للخطر." if impact else ".")
        ),
        "probable_cause_and_confidence": (
            f"{hypothesis.statement} (مستوى الثقة {hypothesis.confidence:.0%})"
            if hypothesis else "لم يتم تحديد فرضية للسبب الجذري بعد."
        ),
        "what_rased_did": _what_rased_did_ar(state),
        "needs_from_human": _needed_from_human_ar(state),
    }

    return {"en": en, "ar": ar}


__all__ = ["build_bilingual_brief"]
