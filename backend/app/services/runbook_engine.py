"""
FalconOps AI - Runbook Automation Engine
Enterprise-grade runbook execution with multiple action types
"""
import uuid
import asyncio
import subprocess
import shlex
import httpx
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum

from ..core.database import db


class ActionType(str, Enum):
    """Supported runbook action types"""
    HTTP_REQUEST = "http_request"
    SHELL_COMMAND = "shell_command"
    SSH_COMMAND = "ssh_command"
    DATABASE_QUERY = "database_query"
    NOTIFICATION = "notification"
    DELAY = "delay"
    CONDITION = "condition"
    WEBHOOK = "webhook"
    LOG_MESSAGE = "log_message"
    METRIC_CHECK = "metric_check"
    SERVICE_RESTART = "service_restart"
    APPROVAL = "approval"
    # New action types
    KUBERNETES = "kubernetes"
    SCRIPT = "script"
    SET_VARIABLE = "set_variable"
    LOOP = "loop"
    PARALLEL = "parallel"
    CALL_AGENT = "call_agent"


class RunbookEngine:
    """
    Enterprise Runbook Automation Engine
    Executes runbook steps with full audit trail and rollback support
    """
    
    def __init__(self):
        self.execution_context: Dict[str, Any] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute_runbook(
        self,
        runbook_id: str,
        trigger_source: str = "manual",
        trigger_context: Dict[str, Any] = None,
        user_email: str = "system",
        tenant_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a complete runbook with all steps
        Returns execution result with detailed step-by-step outcomes

        entity_id/entity_type/entity_name are optional additions for the
        Resource Explorer's "Execute Runbook against Resource X" action —
        backward compatible: existing callers passing none of these are
        completely unaffected (_interpolate_variables() already falls back to
        the literal {{placeholder}} text for any unresolved template variable).
        """
        runbook = await db.runbooks.find_one({"id": runbook_id}, {"_id": 0})
        if not runbook:
            return {"success": False, "error": "Runbook not found"}

        execution_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        # Initialize execution record
        execution_doc = {
            "id": execution_id,
            "runbook_id": runbook_id,
            "runbook_name": runbook["name"],
            "trigger_source": trigger_source,
            "trigger_context": trigger_context or {},
            "executed_by": user_email,
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "entity_name": entity_name,
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "steps_total": len(runbook.get("steps", [])),
            "steps_completed": 0,
            "steps_failed": 0,
            "step_results": [],
            "variables": {},
            "error_message": None
        }

        await db.runbook_executions.insert_one(execution_doc)

        # Execute each step
        self.execution_context = {
            "execution_id": execution_id,
            "runbook_id": runbook_id,
            "variables": trigger_context or {},
            "step_outputs": {}
        }
        # setdefault, not overwrite — a runbook template's own trigger_context
        # value for these keys (if any) takes precedence over the resource link.
        for _k, _v in (("entity_id", entity_id), ("entity_type", entity_type), ("entity_name", entity_name)):
            if _v is not None:
                self.execution_context["variables"].setdefault(_k, _v)
        
        all_success = True
        steps_completed = 0
        step_results = []
        
        for idx, step in enumerate(runbook.get("steps", [])):
            step_result = await self._execute_step(step, idx + 1)
            step_results.append(step_result)
            
            if step_result["status"] == "success":
                steps_completed += 1
                # Store step output for later steps
                self.execution_context["step_outputs"][f"step_{idx + 1}"] = step_result.get("output", {})
            else:
                all_success = False
                # Check if step is marked as continue_on_failure
                if not step.get("continue_on_failure", False):
                    break
        
        # Update execution record
        completed_at = datetime.now(timezone.utc).isoformat()
        final_status = "completed" if all_success else "failed"
        
        await db.runbook_executions.update_one(
            {"id": execution_id},
            {
                "$set": {
                    "status": final_status,
                    "completed_at": completed_at,
                    "steps_completed": steps_completed,
                    "steps_failed": len(step_results) - steps_completed,
                    "step_results": step_results,
                    "variables": self.execution_context.get("variables", {})
                }
            }
        )
        
        # Update runbook stats
        await db.runbooks.update_one(
            {"id": runbook_id},
            {
                "$set": {"last_executed": completed_at},
                "$inc": {"execution_count": 1}
            }
        )
        
        return {
            "success": all_success,
            "execution_id": execution_id,
            "status": final_status,
            "steps_completed": steps_completed,
            "steps_total": len(runbook.get("steps", [])),
            "step_results": step_results,
            "started_at": started_at,
            "completed_at": completed_at
        }
    
    async def _execute_step(self, step: Dict[str, Any], step_number: int) -> Dict[str, Any]:
        """Execute a single runbook step"""
        action_type = step.get("action_type", step.get("action", "unknown"))
        step_name = step.get("name", f"Step {step_number}")
        started_at = datetime.now(timezone.utc).isoformat()
        
        result = {
            "step_number": step_number,
            "name": step_name,
            "action_type": action_type,
            "status": "pending",
            "started_at": started_at,
            "completed_at": None,
            "output": {},
            "error": None
        }
        
        try:
            # Route to appropriate handler
            if action_type == ActionType.HTTP_REQUEST or action_type == "http_request":
                output = await self._execute_http_request(step)
            elif action_type == ActionType.SHELL_COMMAND or action_type == "shell_command":
                output = await self._execute_shell_command(step)
            elif action_type == ActionType.DELAY or action_type == "delay":
                output = await self._execute_delay(step)
            elif action_type == ActionType.NOTIFICATION or action_type == "notification":
                output = await self._execute_notification(step)
            elif action_type == ActionType.WEBHOOK or action_type == "webhook":
                output = await self._execute_webhook(step)
            elif action_type == ActionType.LOG_MESSAGE or action_type == "log_message":
                output = await self._execute_log_message(step)
            elif action_type == ActionType.CONDITION or action_type == "condition":
                output = await self._execute_condition(step)
            elif action_type == ActionType.METRIC_CHECK or action_type == "metric_check":
                output = await self._execute_metric_check(step)
            elif action_type == ActionType.SERVICE_RESTART or action_type == "service_restart":
                output = await self._execute_service_restart(step)
            elif action_type == ActionType.APPROVAL or action_type == "approval":
                output = await self._execute_approval(step)
            elif action_type == ActionType.SSH_COMMAND or action_type == "ssh_command":
                output = await self._execute_ssh_command(step)
            elif action_type == ActionType.DATABASE_QUERY or action_type == "database_query":
                output = await self._execute_database_query(step)
            elif action_type == ActionType.KUBERNETES or action_type == "kubernetes":
                output = await self._execute_kubernetes(step)
            elif action_type == ActionType.SCRIPT or action_type == "script":
                output = await self._execute_script(step)
            elif action_type == ActionType.SET_VARIABLE or action_type == "set_variable":
                output = await self._execute_set_variable(step)
            elif action_type == ActionType.LOOP or action_type == "loop":
                output = await self._execute_loop(step)
            elif action_type == ActionType.PARALLEL or action_type == "parallel":
                output = await self._execute_parallel(step)
            elif action_type == ActionType.CALL_AGENT or action_type == "call_agent":
                output = await self._execute_call_agent(step)
            else:
                output = {"message": f"Action type '{action_type}' executed (simulated)"}
            
            result["status"] = "success"
            result["output"] = output
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        return result
    
    async def _execute_http_request(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an HTTP request action"""
        config = step.get("config", {})
        method = config.get("method", "GET").upper()
        url = self._interpolate_variables(config.get("url", ""))
        headers = config.get("headers", {})
        body = config.get("body")
        timeout = config.get("timeout", 30)

        from .ssrf_guard import is_safe_outbound_url
        if not is_safe_outbound_url(url):
            return {"status_code": 0, "response_body": "Refused: URL resolves to a private/internal address",
                    "success": False}

        # Interpolate variables in URL and body
        if body:
            body = self._interpolate_variables(str(body))

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body if method in ["POST", "PUT", "PATCH"] else None
            )
        
        return {
            "status_code": response.status_code,
            "response_body": response.text[:1000],  # Limit response size
            "success": 200 <= response.status_code < 300
        }
    
    async def _execute_shell_command(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command from a strict allowlist. Runs via the list form
        (shell=False) rather than a raw string through a shell — shell metacharacters
        (;, &&, |, backticks, $()) in a step's config can then never break out of the
        allowed command; they just become literal (and typically invalid) arguments to
        it, instead of being interpreted by /bin/sh as previously."""
        config = step.get("config", {})
        command = config.get("command", "echo 'No command specified'")

        safe_commands = ["echo", "date", "whoami", "hostname", "uptime", "df", "free", "ps", "top", "cat", "ls", "pwd"]
        try:
            cmd_parts = shlex.split(command)
        except ValueError:
            return {"command": command, "error": "Could not parse command", "success": False}

        if cmd_parts and cmd_parts[0] in safe_commands:
            try:
                result = subprocess.run(
                    cmd_parts,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "command": command,
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr[:500],
                    "return_code": result.returncode,
                    "success": result.returncode == 0
                }
            except subprocess.TimeoutExpired:
                return {"command": command, "error": "Command timeout", "success": False}
            except Exception as e:
                return {"command": command, "error": str(e)[:300], "success": False}
        else:
            return {
                "command": command,
                "message": "Command simulated (not executed for security)",
                "simulated": True,
                "success": True
            }
    
    async def _execute_delay(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a delay action"""
        config = step.get("config", {})
        seconds = min(config.get("seconds", 5), 60)  # Max 60 seconds
        
        await asyncio.sleep(seconds)
        
        return {
            "delayed_seconds": seconds,
            "success": True
        }
    
    async def _execute_notification(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Send a notification"""
        config = step.get("config", {})
        channel = config.get("channel", "log")
        message = self._interpolate_variables(config.get("message", "Notification"))
        recipients = config.get("recipients", [])
        
        # Log the notification
        notification_doc = {
            "id": str(uuid.uuid4()),
            "execution_id": self.execution_context.get("execution_id"),
            "channel": channel,
            "message": message,
            "recipients": recipients,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "status": "sent"
        }
        
        await db.runbook_notifications.insert_one(notification_doc)
        
        return {
            "channel": channel,
            "message": message,
            "recipients": recipients,
            "notification_id": notification_doc["id"],
            "success": True
        }
    
    async def _execute_webhook(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Send a webhook"""
        config = step.get("config", {})
        url = self._interpolate_variables(config.get("url", ""))
        payload = config.get("payload", {})
        
        # Interpolate variables in payload
        payload_str = json.dumps(payload)
        payload_str = self._interpolate_variables(payload_str)
        payload = json.loads(payload_str)
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
        
        return {
            "url": url,
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300
        }
    
    async def _execute_log_message(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Log a message"""
        config = step.get("config", {})
        message = self._interpolate_variables(config.get("message", "Log entry"))
        level = config.get("level", "info")
        
        log_doc = {
            "id": str(uuid.uuid4()),
            "execution_id": self.execution_context.get("execution_id"),
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await db.runbook_logs.insert_one(log_doc)
        
        return {
            "level": level,
            "message": message,
            "success": True
        }
    
    async def _execute_condition(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a condition"""
        config = step.get("config", {})
        condition_type = config.get("type", "equals")
        left_value = self._interpolate_variables(str(config.get("left", "")))
        right_value = self._interpolate_variables(str(config.get("right", "")))
        
        result = False
        if condition_type == "equals":
            result = left_value == right_value
        elif condition_type == "not_equals":
            result = left_value != right_value
        elif condition_type == "contains":
            result = right_value in left_value
        elif condition_type == "greater_than":
            try:
                result = float(left_value) > float(right_value)
            except ValueError:
                result = False
        elif condition_type == "less_than":
            try:
                result = float(left_value) < float(right_value)
            except ValueError:
                result = False
        elif condition_type == "regex":
            import re
            try:
                result = bool(re.search(right_value, left_value))
            except:
                result = False
        
        return {
            "condition_type": condition_type,
            "left_value": left_value,
            "right_value": right_value,
            "result": result,
            "success": result
        }
    
    async def _execute_metric_check(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Check a metric value"""
        config = step.get("config", {})
        metric_name = config.get("metric", "cpu_usage")
        threshold = config.get("threshold", 80)
        operator = config.get("operator", "less_than")
        server_id = config.get("server_id")
        
        # Get latest metric from database
        query = {"metric_name": metric_name}
        if server_id:
            query["server_id"] = server_id
        
        metric = await db.server_metrics.find_one(
            query,
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        
        current_value = metric.get("value", 0) if metric else 0
        
        passed = False
        if operator == "less_than":
            passed = current_value < threshold
        elif operator == "greater_than":
            passed = current_value > threshold
        elif operator == "equals":
            passed = current_value == threshold
        
        return {
            "metric": metric_name,
            "current_value": current_value,
            "threshold": threshold,
            "operator": operator,
            "passed": passed,
            "success": passed
        }
    
    async def _execute_service_restart(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a service restart"""
        config = step.get("config", {})
        service_name = config.get("service", "unknown-service")
        
        # Log the restart attempt
        restart_doc = {
            "id": str(uuid.uuid4()),
            "execution_id": self.execution_context.get("execution_id"),
            "service": service_name,
            "action": "restart",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "simulated"
        }
        
        await db.runbook_actions.insert_one(restart_doc)
        
        return {
            "service": service_name,
            "action": "restart",
            "message": f"Service '{service_name}' restart initiated (simulated)",
            "simulated": True,
            "success": True
        }
    
    async def _execute_approval(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Create an approval request"""
        config = step.get("config", {})
        approvers = config.get("approvers", [])
        message = config.get("message", "Approval required to continue")
        timeout_minutes = config.get("timeout_minutes", 60)
        
        approval_doc = {
            "id": str(uuid.uuid4()),
            "execution_id": self.execution_context.get("execution_id"),
            "approvers": approvers,
            "message": message,
            "timeout_minutes": timeout_minutes,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "approved_by": None,
            "approved_at": None
        }
        
        await db.runbook_approvals.insert_one(approval_doc)
        
        # For demo, auto-approve
        return {
            "approval_id": approval_doc["id"],
            "message": message,
            "approvers": approvers,
            "auto_approved": True,
            "success": True
        }
    
    async def _execute_ssh_command(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute SSH command (simulated for security)"""
        config = step.get("config", {})
        host = self._interpolate_variables(config.get("host", ""))
        username = config.get("username", "root")
        command = self._interpolate_variables(config.get("command", ""))
        port = config.get("port", 22)
        
        # Simulated execution for security
        return {
            "host": host,
            "username": username,
            "port": port,
            "command": command,
            "message": f"SSH command simulated on {username}@{host}:{port}",
            "simulated": True,
            "stdout": f"[Simulated output for: {command}]",
            "success": True
        }
    
    async def _execute_database_query(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database query (simulated for security)"""
        config = step.get("config", {})
        database_type = config.get("database_type", "mongodb")
        query = self._interpolate_variables(config.get("query", ""))
        database = config.get("database", "")
        
        # Simulated execution for security
        return {
            "database_type": database_type,
            "database": database,
            "query": query,
            "message": f"Database query simulated on {database_type}:{database}",
            "simulated": True,
            "rows_affected": 0,
            "success": True
        }
    
    async def _execute_kubernetes(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Kubernetes command (simulated)"""
        config = step.get("config", {})
        action = config.get("action", "get")  # get, apply, delete, rollout, scale
        resource_type = config.get("resource_type", "pods")  # pods, deployments, services, etc.
        resource_name = self._interpolate_variables(config.get("resource_name", ""))
        namespace = config.get("namespace", "default")
        replicas = config.get("replicas")
        
        # Build kubectl command
        if action == "get":
            cmd = f"kubectl get {resource_type} {resource_name} -n {namespace}"
        elif action == "delete":
            cmd = f"kubectl delete {resource_type} {resource_name} -n {namespace}"
        elif action == "rollout_restart":
            cmd = f"kubectl rollout restart {resource_type}/{resource_name} -n {namespace}"
        elif action == "scale":
            cmd = f"kubectl scale {resource_type}/{resource_name} --replicas={replicas} -n {namespace}"
        elif action == "logs":
            cmd = f"kubectl logs {resource_name} -n {namespace} --tail=100"
        elif action == "describe":
            cmd = f"kubectl describe {resource_type} {resource_name} -n {namespace}"
        else:
            cmd = f"kubectl {action} {resource_type} {resource_name} -n {namespace}"
        
        return {
            "action": action,
            "resource_type": resource_type,
            "resource_name": resource_name,
            "namespace": namespace,
            "command": cmd,
            "message": f"Kubernetes command simulated: {cmd}",
            "simulated": True,
            "success": True
        }
    
    async def _execute_script(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a script (Python/Bash - simulated)"""
        config = step.get("config", {})
        script_type = config.get("script_type", "bash")  # bash, python
        script_content = self._interpolate_variables(config.get("script", ""))
        
        return {
            "script_type": script_type,
            "script_length": len(script_content),
            "message": f"{script_type.capitalize()} script simulated ({len(script_content)} chars)",
            "simulated": True,
            "success": True
        }
    
    async def _execute_set_variable(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Set a variable for use in subsequent steps"""
        config = step.get("config", {})
        variable_name = config.get("name", "")
        variable_value = self._interpolate_variables(str(config.get("value", "")))
        
        # Store in execution context
        self.execution_context["variables"][variable_name] = variable_value
        
        return {
            "variable_name": variable_name,
            "variable_value": variable_value,
            "message": f"Variable '{variable_name}' set to '{variable_value}'",
            "success": True
        }
    
    async def _execute_loop(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a loop over items"""
        config = step.get("config", {})
        items = config.get("items", [])
        max_iterations = min(config.get("max_iterations", 10), 100)
        
        results = []
        for i, item in enumerate(items[:max_iterations]):
            results.append({
                "iteration": i + 1,
                "item": item,
                "status": "completed"
            })
        
        return {
            "iterations_completed": len(results),
            "max_iterations": max_iterations,
            "results": results,
            "success": True
        }
    
    async def _execute_parallel(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multiple actions in parallel (simulated)"""
        config = step.get("config", {})
        actions = config.get("actions", [])
        
        results = []
        for i, action in enumerate(actions):
            results.append({
                "action_index": i + 1,
                "action_type": action.get("action_type", "unknown"),
                "status": "completed (simulated)"
            })
        
        return {
            "parallel_actions": len(actions),
            "results": results,
            "message": f"Executed {len(actions)} actions in parallel (simulated)",
            "simulated": True,
            "success": True
        }
    
    async def _execute_call_agent(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a specialized AI agent and capture its findings for downstream steps
        (e.g. a following notification step referencing {{stepN.narrative}} to
        'annotate' the triggering problem — mirrors the trigger -> call_agent ->
        agent_report shape from the workflow builder's canvas)."""
        config = step.get("config", {})
        agent_source = config.get("agent_source", "security")
        agent_id = config.get("agent_id", "")
        query = self._interpolate_variables(config.get("query_template", "Analyze this incident."))

        if agent_source == "security":
            from .security_agents_service import run_security_agent
            tenant_id = self.execution_context.get("variables", {}).get("tenant_id")
            result = await run_security_agent(agent_id, query, tenant_id=tenant_id)
            if not result:
                return {"agent_source": agent_source, "agent_id": agent_id, "success": False,
                         "error": f"Unknown security agent '{agent_id}'"}
            return {
                "agent_source": agent_source,
                "agent_id": agent_id,
                "agent_name": result.get("agent_name"),
                "narrative": result.get("summary", ""),
                "confidence": result.get("confidence"),
                "recommended_actions": result.get("recommended_actions", []),
                "success": True,
            }
        elif agent_source == "core":
            from .ai_agents_service import run_agent
            result = await run_agent(agent_id, {"description": query})
            if "error" in result:
                return {"agent_source": agent_source, "agent_id": agent_id, "success": False,
                         "error": result["error"]}
            return {
                "agent_source": agent_source,
                "agent_id": agent_id,
                "agent_name": result.get("agent_name"),
                "narrative": result.get("analysis", ""),
                "success": True,
            }
        elif agent_source == "ops":
            from .ops_agents_service import run_ops_agent
            tenant_id = self.execution_context.get("variables", {}).get("tenant_id")
            result = await run_ops_agent(agent_id, query, tenant_id=tenant_id)
            if not result:
                return {"agent_source": agent_source, "agent_id": agent_id, "success": False,
                         "error": f"Unknown ops agent '{agent_id}'"}
            return {
                "agent_source": agent_source,
                "agent_id": agent_id,
                "agent_name": result.get("agent_name"),
                "narrative": result.get("summary", ""),
                "confidence": result.get("confidence"),
                "recommended_actions": result.get("recommended_actions", []),
                "success": True,
            }
        else:
            return {"agent_source": agent_source, "success": False,
                     "error": f"Unknown agent_source '{agent_source}' (expected 'security', 'core', or 'ops')"}

    def _interpolate_variables(self, text: str) -> str:
        """Replace {{variable}} placeholders with actual values. Supports one level of
        dot-path access into a step's output dict (e.g. {{step_1.narrative}}) so a
        call_agent step's findings can be referenced by a later notification/
        log_message step — falls back to stringifying the whole value for a bare
        {{key}} placeholder, preserving behavior for every existing template."""
        if not text or "{{" not in text:
            return text

        import re
        variables = self.execution_context.get("variables", {})
        step_outputs = self.execution_context.get("step_outputs", {})
        all_vars = {**variables, **step_outputs}

        def _resolve(match):
            parts = match.group(1).strip().split(".")
            value = all_vars.get(parts[0])
            if value is None:
                return match.group(0)
            for part in parts[1:]:
                value = value.get(part) if isinstance(value, dict) else None
                if value is None:
                    return match.group(0)
            return str(value)

        return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", _resolve, text)


# Singleton instance
runbook_engine = RunbookEngine()


async def get_runbook_templates() -> List[Dict[str, Any]]:
    """Get predefined runbook templates"""
    return [
        # Infrastructure Templates
        {
            "id": "tpl-high-cpu",
            "name": "High CPU Remediation",
            "description": "Automatically remediate high CPU issues",
            "category": "infrastructure",
            "steps": [
                {
                    "name": "Check CPU Metrics",
                    "action_type": "metric_check",
                    "config": {
                        "metric": "cpu_usage",
                        "threshold": 90,
                        "operator": "greater_than"
                    }
                },
                {
                    "name": "Notify Team",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "High CPU detected on {{server_name}}",
                        "recipients": ["ops-team"]
                    }
                },
                {
                    "name": "Restart Service",
                    "action_type": "service_restart",
                    "config": {
                        "service": "{{affected_service}}"
                    },
                    "continue_on_failure": True
                }
            ]
        },
        {
            "id": "tpl-disk-cleanup",
            "name": "Disk Space Cleanup",
            "description": "Clean up disk space when threshold exceeded",
            "category": "infrastructure",
            "steps": [
                {
                    "name": "Check Disk Space",
                    "action_type": "metric_check",
                    "config": {
                        "metric": "disk_usage",
                        "threshold": 85,
                        "operator": "greater_than"
                    }
                },
                {
                    "name": "Clean Temp Files",
                    "action_type": "shell_command",
                    "config": {
                        "command": "echo 'Cleaning temp files...'"
                    }
                },
                {
                    "name": "Log Cleanup",
                    "action_type": "log_message",
                    "config": {
                        "level": "info",
                        "message": "Disk cleanup completed"
                    }
                }
            ]
        },
        {
            "id": "tpl-memory-leak",
            "name": "Memory Leak Detection",
            "description": "Detect and remediate memory leaks",
            "category": "infrastructure",
            "steps": [
                {
                    "name": "Check Memory Usage",
                    "action_type": "metric_check",
                    "config": {
                        "metric": "memory_usage",
                        "threshold": 90,
                        "operator": "greater_than"
                    }
                },
                {
                    "name": "Capture Memory Stats",
                    "action_type": "shell_command",
                    "config": {
                        "command": "free -m"
                    }
                },
                {
                    "name": "Alert Team",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "Memory leak detected: {{server_name}} at {{memory_usage}}%",
                        "recipients": ["dev-team"]
                    }
                },
                {
                    "name": "Restart Application",
                    "action_type": "service_restart",
                    "config": {
                        "service": "{{affected_service}}"
                    }
                }
            ]
        },
        # Monitoring Templates
        {
            "id": "tpl-health-check",
            "name": "Service Health Check",
            "description": "Comprehensive health check with notifications",
            "category": "monitoring",
            "steps": [
                {
                    "name": "Check API Endpoint",
                    "action_type": "http_request",
                    "config": {
                        "method": "GET",
                        "url": "{{service_url}}/health",
                        "timeout": 10
                    }
                },
                {
                    "name": "Verify Response",
                    "action_type": "condition",
                    "config": {
                        "type": "equals",
                        "left": "{{step_1.status_code}}",
                        "right": "200"
                    }
                },
                {
                    "name": "Send Status",
                    "action_type": "webhook",
                    "config": {
                        "url": "{{callback_url}}",
                        "payload": {"status": "healthy"}
                    }
                }
            ]
        },
        {
            "id": "tpl-ssl-check",
            "name": "SSL Certificate Check",
            "description": "Monitor SSL certificate expiry",
            "category": "monitoring",
            "steps": [
                {
                    "name": "Check Certificate",
                    "action_type": "http_request",
                    "config": {
                        "method": "GET",
                        "url": "https://{{domain}}",
                        "timeout": 10
                    }
                },
                {
                    "name": "Log Check Result",
                    "action_type": "log_message",
                    "config": {
                        "level": "info",
                        "message": "SSL certificate check completed for {{domain}}"
                    }
                },
                {
                    "name": "Notify if Expiring",
                    "action_type": "notification",
                    "config": {
                        "channel": "email",
                        "message": "SSL certificate for {{domain}} needs attention",
                        "recipients": ["security@company.com"]
                    },
                    "continue_on_failure": True
                }
            ]
        },
        # Incident Templates
        {
            "id": "tpl-incident-response",
            "name": "Incident Response Workflow",
            "description": "Automated incident response with escalation",
            "category": "incident",
            "steps": [
                {
                    "name": "Create Incident Ticket",
                    "action_type": "log_message",
                    "config": {
                        "level": "critical",
                        "message": "Incident detected: {{incident_title}}"
                    }
                },
                {
                    "name": "Notify On-Call",
                    "action_type": "notification",
                    "config": {
                        "channel": "pagerduty",
                        "message": "Critical incident: {{incident_title}}",
                        "recipients": ["on-call"]
                    }
                },
                {
                    "name": "Wait for Response",
                    "action_type": "delay",
                    "config": {
                        "seconds": 30
                    }
                },
                {
                    "name": "Escalate if Needed",
                    "action_type": "approval",
                    "config": {
                        "approvers": ["manager@company.com"],
                        "message": "Escalation needed for {{incident_title}}",
                        "timeout_minutes": 15
                    }
                }
            ]
        },
        {
            "id": "tpl-outage-response",
            "name": "Outage Response",
            "description": "Full outage response workflow",
            "category": "incident",
            "steps": [
                {
                    "name": "Acknowledge Outage",
                    "action_type": "log_message",
                    "config": {
                        "level": "critical",
                        "message": "OUTAGE: {{service_name}} is down"
                    }
                },
                {
                    "name": "Page On-Call",
                    "action_type": "notification",
                    "config": {
                        "channel": "pagerduty",
                        "message": "URGENT: {{service_name}} outage detected",
                        "recipients": ["on-call", "engineering-lead"]
                    }
                },
                {
                    "name": "Update Status Page",
                    "action_type": "webhook",
                    "config": {
                        "url": "{{statuspage_url}}/incidents",
                        "payload": {
                            "name": "{{service_name}} Outage",
                            "status": "investigating"
                        }
                    }
                },
                {
                    "name": "Attempt Auto-Recovery",
                    "action_type": "service_restart",
                    "config": {
                        "service": "{{service_name}}"
                    },
                    "continue_on_failure": True
                }
            ]
        },
        # Deployment Templates
        {
            "id": "tpl-deployment",
            "name": "Deployment Validation",
            "description": "Validate deployment health after release",
            "category": "deployment",
            "steps": [
                {
                    "name": "Wait for Startup",
                    "action_type": "delay",
                    "config": {
                        "seconds": 10
                    }
                },
                {
                    "name": "Health Check",
                    "action_type": "http_request",
                    "config": {
                        "method": "GET",
                        "url": "{{app_url}}/api/health",
                        "timeout": 30
                    }
                },
                {
                    "name": "Notify Success",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "Deployment successful: {{app_name}} v{{version}}"
                    }
                }
            ]
        },
        {
            "id": "tpl-k8s-rollout",
            "name": "Kubernetes Rollout",
            "description": "Rolling update for Kubernetes deployments",
            "category": "deployment",
            "steps": [
                {
                    "name": "Initiate Rollout",
                    "action_type": "kubernetes",
                    "config": {
                        "action": "rollout_restart",
                        "resource_type": "deployment",
                        "resource_name": "{{deployment_name}}",
                        "namespace": "{{namespace}}"
                    }
                },
                {
                    "name": "Wait for Rollout",
                    "action_type": "delay",
                    "config": {
                        "seconds": 30
                    }
                },
                {
                    "name": "Verify Pods",
                    "action_type": "kubernetes",
                    "config": {
                        "action": "get",
                        "resource_type": "pods",
                        "resource_name": "",
                        "namespace": "{{namespace}}"
                    }
                },
                {
                    "name": "Notify Completion",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "Kubernetes rollout complete: {{deployment_name}}"
                    }
                }
            ]
        },
        # Database Templates
        {
            "id": "tpl-db-backup",
            "name": "Database Backup",
            "description": "Automated database backup workflow",
            "category": "database",
            "steps": [
                {
                    "name": "Set Backup Name",
                    "action_type": "set_variable",
                    "config": {
                        "name": "backup_name",
                        "value": "backup_{{database}}_{{timestamp}}"
                    }
                },
                {
                    "name": "Notify Start",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "Starting backup: {{backup_name}}"
                    }
                },
                {
                    "name": "Execute Backup",
                    "action_type": "database_query",
                    "config": {
                        "database_type": "{{db_type}}",
                        "database": "{{database}}",
                        "query": "BACKUP DATABASE {{database}} TO '{{backup_path}}/{{backup_name}}'"
                    }
                },
                {
                    "name": "Verify Backup",
                    "action_type": "shell_command",
                    "config": {
                        "command": "ls -la {{backup_path}}"
                    }
                },
                {
                    "name": "Notify Complete",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "Backup completed: {{backup_name}}"
                    }
                }
            ]
        },
        {
            "id": "tpl-db-maintenance",
            "name": "Database Maintenance",
            "description": "Regular database maintenance tasks",
            "category": "database",
            "steps": [
                {
                    "name": "Check Connections",
                    "action_type": "database_query",
                    "config": {
                        "database_type": "{{db_type}}",
                        "query": "SELECT COUNT(*) FROM pg_stat_activity"
                    }
                },
                {
                    "name": "Vacuum Database",
                    "action_type": "database_query",
                    "config": {
                        "database_type": "postgresql",
                        "database": "{{database}}",
                        "query": "VACUUM ANALYZE"
                    }
                },
                {
                    "name": "Log Completion",
                    "action_type": "log_message",
                    "config": {
                        "level": "info",
                        "message": "Database maintenance completed for {{database}}"
                    }
                }
            ]
        },
        # Security Templates
        {
            "id": "tpl-security-scan",
            "name": "Security Vulnerability Scan",
            "description": "Run security vulnerability scan",
            "category": "security",
            "steps": [
                {
                    "name": "Start Scan",
                    "action_type": "log_message",
                    "config": {
                        "level": "info",
                        "message": "Starting security scan for {{target}}"
                    }
                },
                {
                    "name": "Run Scan",
                    "action_type": "http_request",
                    "config": {
                        "method": "POST",
                        "url": "{{scanner_url}}/api/scan",
                        "body": {"target": "{{target}}"}
                    }
                },
                {
                    "name": "Wait for Results",
                    "action_type": "delay",
                    "config": {
                        "seconds": 30
                    }
                },
                {
                    "name": "Report Results",
                    "action_type": "notification",
                    "config": {
                        "channel": "email",
                        "message": "Security scan completed for {{target}}",
                        "recipients": ["security-team@company.com"]
                    }
                }
            ]
        },
        {
            "id": "tpl-access-audit",
            "name": "Access Audit",
            "description": "Audit user access permissions",
            "category": "security",
            "steps": [
                {
                    "name": "Log Audit Start",
                    "action_type": "log_message",
                    "config": {
                        "level": "info",
                        "message": "Starting access audit for {{system}}"
                    }
                },
                {
                    "name": "Query User List",
                    "action_type": "database_query",
                    "config": {
                        "database_type": "mongodb",
                        "query": "db.users.find({active: true})"
                    }
                },
                {
                    "name": "Generate Report",
                    "action_type": "webhook",
                    "config": {
                        "url": "{{report_url}}/generate",
                        "payload": {"type": "access_audit", "system": "{{system}}"}
                    }
                }
            ]
        },
        # Network Templates
        {
            "id": "tpl-network-health",
            "name": "Network Health Check",
            "description": "Check network connectivity and latency",
            "category": "network",
            "steps": [
                {
                    "name": "Ping Gateway",
                    "action_type": "shell_command",
                    "config": {
                        "command": "echo 'Pinging gateway...'"
                    }
                },
                {
                    "name": "Check DNS",
                    "action_type": "http_request",
                    "config": {
                        "method": "GET",
                        "url": "https://{{dns_target}}",
                        "timeout": 5
                    }
                },
                {
                    "name": "Log Results",
                    "action_type": "log_message",
                    "config": {
                        "level": "info",
                        "message": "Network health check completed"
                    }
                }
            ]
        },
        # AI Agent Templates — each wires a trigger + a call_agent step to one of
        # FalconOps' real specialized agents (security_agents_service / ai_agents_service),
        # matching the workflow builder's trigger -> call_agent -> agent_report shape.
        {
            "id": "tpl-threat-triage-agent",
            "name": "Threat Triage Agent",
            "description": "On every critical/high problem, runs the Threat Hunting Agent and posts its findings",
            "category": "agent",
            "trigger": {
                "type": "problem",
                "problem_filter": {"severity": ["critical", "high"]}
            },
            "steps": [
                {
                    "name": "Run Threat Hunting Agent",
                    "action_type": "call_agent",
                    "config": {
                        "agent_source": "security",
                        "agent_id": "threat_hunting",
                        "query_template": "Investigate this problem for signs of compromise: {{title}} ({{severity}}) on {{service}}"
                    }
                },
                {
                    "name": "Post Findings",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "Threat Hunting Agent findings: {{step_1.narrative}}"
                    },
                    "continue_on_failure": True
                }
            ]
        },
        {
            "id": "tpl-vulnerability-verification-agent",
            "name": "Vulnerability Verification Agent",
            "description": "Daily run of the Cloud Security Agent against current vulnerability + topology data",
            "category": "agent",
            "trigger": {
                "type": "schedule",
                "schedule": {"mode": "cron", "cron_expression": "0 6 * * *"}
            },
            "steps": [
                {
                    "name": "Run Cloud Security Agent",
                    "action_type": "call_agent",
                    "config": {
                        "agent_source": "security",
                        "agent_id": "cloud_security",
                        "query_template": "Review current CVE exposure against our service topology and prioritize the top risks."
                    }
                },
                {
                    "name": "Post Findings",
                    "action_type": "notification",
                    "config": {
                        "channel": "email",
                        "message": "Vulnerability Verification Agent report: {{step_1.narrative}}"
                    },
                    "continue_on_failure": True
                }
            ]
        },
        {
            "id": "tpl-identity-risk-agent",
            "name": "Identity Risk Agent",
            "description": "On every problem, runs the Identity Security Agent to check for credential/insider-threat risk",
            "category": "agent",
            "trigger": {
                "type": "problem",
                "problem_filter": {"severity": ["critical", "high", "medium"]}
            },
            "steps": [
                {
                    "name": "Run Identity Security Agent",
                    "action_type": "call_agent",
                    "config": {
                        "agent_source": "security",
                        "agent_id": "identity",
                        "query_template": "Assess identity-based risk (credential compromise, privilege escalation, insider threat) related to: {{title}}"
                    }
                }
            ]
        },
        {
            "id": "tpl-compliance-check-agent",
            "name": "Compliance Check Agent",
            "description": "Weekly run of the Compliance Agent across SOC2/ISO27001 controls",
            "category": "agent",
            "trigger": {
                "type": "schedule",
                "schedule": {"mode": "cron", "cron_expression": "0 8 * * 1"}
            },
            "steps": [
                {
                    "name": "Run Compliance Agent",
                    "action_type": "call_agent",
                    "config": {
                        "agent_source": "security",
                        "agent_id": "compliance",
                        "query_template": "Assess current SOC2/ISO27001 compliance posture and flag any control gaps."
                    }
                },
                {
                    "name": "Post Findings",
                    "action_type": "notification",
                    "config": {
                        "channel": "email",
                        "message": "Compliance Check Agent report: {{step_1.narrative}}"
                    },
                    "continue_on_failure": True
                }
            ]
        },
        {
            "id": "tpl-network-anomaly-agent",
            "name": "Network Anomaly Agent",
            "description": "On AI-detected anomalies, runs the Network Security Agent to investigate traffic patterns",
            "category": "agent",
            "trigger": {
                "type": "ai_anomaly",
                "anomaly_filter": {"min_severity": "medium"}
            },
            "steps": [
                {
                    "name": "Run Network Security Agent",
                    "action_type": "call_agent",
                    "config": {
                        "agent_source": "security",
                        "agent_id": "network",
                        "query_template": "Analyze this anomaly for network-level attack patterns: {{message}}"
                    }
                }
            ]
        },
        {
            "id": "tpl-incident-rca-agent",
            "name": "Incident RCA Agent",
            "description": "On every critical problem, runs the core RCA Agent and posts a root-cause summary",
            "category": "agent",
            "trigger": {
                "type": "problem",
                "problem_filter": {"severity": ["critical"]}
            },
            "steps": [
                {
                    "name": "Run RCA Agent",
                    "action_type": "call_agent",
                    "config": {
                        "agent_source": "core",
                        "agent_id": "rca",
                        "query_template": "{{title}} affecting {{service}}, severity {{severity}}"
                    }
                },
                {
                    "name": "Post Findings",
                    "action_type": "notification",
                    "config": {
                        "channel": "slack",
                        "message": "RCA Agent analysis: {{step_1.narrative}}"
                    },
                    "continue_on_failure": True
                }
            ]
        }
    ]


async def get_action_types() -> List[Dict[str, Any]]:
    """Get all available action types with descriptions"""
    return [
        {"id": "http_request", "name": "HTTP Request", "description": "Make HTTP/REST API calls", "icon": "globe"},
        {"id": "shell_command", "name": "Shell Command", "description": "Execute shell commands", "icon": "terminal"},
        {"id": "ssh_command", "name": "SSH Command", "description": "Execute commands via SSH", "icon": "key"},
        {"id": "database_query", "name": "Database Query", "description": "Execute database queries", "icon": "database"},
        {"id": "notification", "name": "Notification", "description": "Send notifications", "icon": "bell"},
        {"id": "delay", "name": "Delay", "description": "Wait for specified time", "icon": "clock"},
        {"id": "condition", "name": "Condition", "description": "Evaluate conditions", "icon": "git-branch"},
        {"id": "webhook", "name": "Webhook", "description": "Send webhook payloads", "icon": "webhook"},
        {"id": "log_message", "name": "Log Message", "description": "Write log entries", "icon": "file-text"},
        {"id": "metric_check", "name": "Metric Check", "description": "Check metric values", "icon": "bar-chart"},
        {"id": "service_restart", "name": "Service Restart", "description": "Restart a service", "icon": "refresh-cw"},
        {"id": "approval", "name": "Approval", "description": "Request approval to continue", "icon": "check-circle"},
        {"id": "kubernetes", "name": "Kubernetes", "description": "Execute kubectl commands", "icon": "box"},
        {"id": "script", "name": "Script", "description": "Execute Python/Bash scripts", "icon": "code"},
        {"id": "set_variable", "name": "Set Variable", "description": "Set runtime variable", "icon": "variable"},
        {"id": "loop", "name": "Loop", "description": "Iterate over items", "icon": "repeat"},
        {"id": "parallel", "name": "Parallel", "description": "Execute actions in parallel", "icon": "layers"},
        {"id": "call_agent", "name": "Call AI Agent", "description": "Invoke a specialized AI agent and capture its findings", "icon": "bot"}
    ]
