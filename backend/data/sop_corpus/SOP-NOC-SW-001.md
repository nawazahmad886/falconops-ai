# SOP-NOC-SW-001 — Software Service Degradation Response

Synthetic reference SOP for RASED. Section headings use a stable
`[SW-001-N]` identifier that PolicyAgent citations point at directly — the
ID does not change if sections are reordered or new ones are inserted.

## [SW-001-1] Purpose and Scope

This procedure governs the Network Operations Center's response to
degradation or failure of any monitored software service — API latency,
error-rate elevation, dependency failure, or resource exhaustion. It applies
to automated and human-initiated investigations alike.

## [SW-001-2] Severity Classification

Severity is assigned from measured business impact, not from alert count or
subjective judgment:

- P1 — Critical: estimated transactions at risk >= 10,000 in the current
  window, or estimated revenue at risk >= $100,000.
- P2 — Significant: estimated transactions at risk >= 2,000.
- P3 — Moderate: estimated transactions at risk >= 200.
- P4 — Low: below the P3 threshold, or fully contained within an approved
  maintenance window.

## [SW-001-3] P1 Critical Escalation Procedure

A P1 classification pages the on-call incident commander immediately,
regardless of time of day. A bridge is opened within five minutes. Any
DESTRUCTIVE-tier remediation action requires explicit human approval before
execution, even under P1 time pressure — severity does not waive the
approval gate defined in SOP-NOC-AD-001 [AD-001-4].

## [SW-001-4] P2 Significant Impact Escalation Procedure

A P2 classification notifies the NOC shift lead, who acknowledges within
fifteen minutes. GUARDED-tier actions may proceed automatically if
confidence is at or above the standard floor; DESTRUCTIVE-tier actions still
require approval.

## [SW-001-5] P3 Standard Response Procedure

A P3 classification is routed to the affected service's on-call owner via
standard ticketing, no page. SAFE and GUARDED actions may auto-execute.

## [SW-001-6] P4 Low Priority Monitoring

A P4 classification is logged for trend analysis only. No page, no ticket
escalation beyond an automated log entry. If P4 was reached because the
affected service is inside an approved maintenance window, see
SOP-NOC-AD-001 [AD-001-5] for suppression handling.

## [SW-001-7] Notification Templates

Each severity tier maps to exactly one notification template
(P1_MAJOR_INCIDENT, P2_SIGNIFICANT_IMPACT, P3_STANDARD_NOTICE,
P4_LOW_PRIORITY_LOG). Templates are selected by severity tier alone — they
are not freely composed per incident, so every notification of a given tier
reads consistently regardless of which engineer or agent triggered it.
