# Live Execution Roadmap (not built — scoped only)

This is the write-up promised when scoping the Problems console's action
buttons: what it would actually take to make "restart process" / "clear
logs" / "restart top consumer" execute for real against a host, instead of
the dry-run preview shipped today (`remediation_service.py`, wired to the
Problems console via `problems_routes.py`'s `/remediate` route). Nothing in
this document is implemented. Read this before deciding to build it.

## Why this is a separate decision, not an incremental add

Every remediation surface in this codebase — `remediation_service.py`,
`k8s_healing_service.py`, `action_broker_schema.py` (whose `execute()`
unconditionally raises `NotImplementedError`) — is dry-run by explicit,
repeated design. There is currently **no execution channel to any real host
anywhere in this stack**: OneAgent (`oneagent/`, `app/routes/oneagent_routes.py`)
is one-way telemetry push only (logs/metrics/traces/netflows/heartbeat up to
the backend) and has no command-polling loop or ability to receive an
instruction. Building real execution means building a new authenticated
command channel from scratch, not flipping a flag.

## What it would require

1. **A command channel in OneAgent itself.** The agent would need to either
   long-poll a new `/api/oneagent/commands/{agent_id}` endpoint on an
   interval, or hold a persistent connection (WebSocket/gRPC stream) the
   backend can push to. Push-based is lower latency but a materially bigger
   change to the agent's connection model (`oneagent/pkg/transport/transport.go`
   currently only knows how to POST outbound).

2. **A command queue + audit trail**, separate from `db.remediation_history`
   (which records *previews*, not *executions*): who requested it, what
   exact command was sent, which agent picked it up, when, and what it
   returned (stdout/stderr/exit code) — this is the actual execution record,
   not a simulated one.

3. **Per-agent authorization, not just per-user.** Today's JWT auth
   (`require_write_access`) proves who's asking; it says nothing about
   *which hosts that command is allowed to reach*. A compromised or
   over-permissioned session should not be able to target arbitrary
   infrastructure. This needs a scoping model (agent groups, host
   allowlists, or per-tenant boundaries) before a single real command ships.

4. **An allowlist of executable actions, not arbitrary shell.** The dry-run
   `ACTION_LIBRARY`'s `script_template` strings are safe *only* because
   they're never actually run. A live executor must not accept a raw
   command string from an HTTP request body — it should dispatch a small,
   fixed set of named operations (`restart_process(name)`,
   `truncate_logs(path)`, ...) that the agent implements natively, so no
   combination of user input can construct an arbitrary command.

5. **An approval gate for anything destructive**, mirroring the pattern
   already built for RASED (`app/services/rased/agents/action.py`): SAFE/
   GUARDED-tier actions may auto-execute under confidence/blast-radius
   gates, DESTRUCTIVE-tier actions always pause for explicit human
   approval before the agent is told to act. `kill_process`/
   `restart_top_consumer` are exactly the kind of action that should never
   auto-fire without one.

6. **Process-level telemetry, for `restart_top_consumer` specifically.**
   OneAgent's collector already has `ProcessStats(pid)`
   (`oneagent/pkg/collector/system.go`) but it's only invoked for PIDs of
   already-discovered services, not exposed as a "rank all processes on
   this host by CPU/memory" capability. Auto-identifying "the top consumer"
   needs this data pipeline built and ingested before the action can target
   a process without an engineer naming it first — a separate, smaller
   telemetry project in its own right, independent of the command-channel
   work above.

7. **Rollback/safety bounds per action type.** A restarted service that
   fails to come back up, or a truncated log file a compliance process
   still needed, are real failure modes a preview never has to account for.
   Each live action needs its own definition of "how do we know it worked"
   and "what do we do if it didn't," not just a fire-and-forget command.

## Suggested order, if this gets prioritized

SAFE-tier only first (`collect_diagnostics`-equivalent, read-only), on a
single pilot host, behind a feature flag — prove the command channel and
audit trail work correctly before anything that mutates state is anywhere
near it. GUARDED-tier (restart/clear) comes after that's solid and reviewed.
DESTRUCTIVE-tier live execution (this library doesn't currently define any
in the Problems-console subset, but the full `ACTION_LIBRARY` has some —
`rotate_credentials`, `disable_user`) should not be attempted until the
approval-gate infrastructure above is built and independently tested.
