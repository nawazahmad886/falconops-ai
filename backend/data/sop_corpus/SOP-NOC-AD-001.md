# SOP-NOC-AD-001 — Automated Diagnostics and Auto-Remediation Authorization

Synthetic reference SOP for RASED. Governs what an autonomous investigation
agent may do without a human in the loop, and what it may never do without
one. Section IDs are stable `[AD-001-N]` identifiers.

## [AD-001-1] Purpose and Scope

This procedure defines the authorization boundary for RASED's automated
investigation and remediation actions, independent of the severity
classification in SOP-NOC-SW-001. Severity decides who gets notified and how
urgently; this document decides what the agent itself is allowed to do.

## [AD-001-2] Action Risk Tiers

Every action available to RASED is declared in a static registry with one of
three risk tiers, never inferred at runtime:

- SAFE — no operational impact if wrong (e.g. suppressing duplicate alerts,
  collecting diagnostics).
- GUARDED — reversible operational impact (e.g. restarting a pod, scaling a
  service out).
- DESTRUCTIVE — hard to reverse or affects shared state (e.g. failing over a
  dependency, rolling back a deployment).

## [AD-001-3] Autonomous Action Authorization Without Human Approval

SAFE and GUARDED actions may execute automatically when confidence is at or
above the standard floor (0.70), there is no active maintenance window for
the target service, and the blast radius does not exceed the threshold in
[AD-001-6]. No human approval step is required for these two tiers under
those conditions.

## [AD-001-4] Mandatory Human Approval for Destructive Actions

A DESTRUCTIVE-tier action always requires explicit human approval before
execution, at any confidence level and regardless of severity tier. The
approval request expires after ten minutes with no response, at which point
it auto-escalates up the chain defined in SOP-NOC-SW-001's escalation
procedure for the incident's severity tier.

## [AD-001-5] Maintenance Window Suppression Policy

If the affected service is inside an approved maintenance window at the time
of the alert, the investigation is suppressed: no action is proposed, no
page is sent, and the event is annotated and logged for later review rather
than escalated. This overrides the severity classification in
SOP-NOC-SW-001 [SW-001-2] for the duration of the window.

## [AD-001-6] Blast Radius Escalation Threshold

If a single investigation's root signature spans more than three distinct
services, RASED does not propose or execute any action regardless of
confidence — it escalates to a human with the full evidence set already
assembled. Acting automatically across that many services at once is judged
too consequential for autonomous execution.

## [AD-001-7] Deployment Correlation Escalation

If a change/deployment record correlates with the onset of degradation
(deployed to the affected service within the lookback window, before
symptom onset), that correlation is surfaced as primary evidence to the
human reviewer even when the proposed remediation itself is only
GUARDED-tier — a recent deployment materially changes what a human should
consider before approving a rollback or restart.
