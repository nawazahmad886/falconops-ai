"""
FalconOps AI - SaaS Billing Routes (Stripe)
Subscription billing with Free/Pro/Enterprise tiers
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..core.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Billing"])

# ======================== PLAN DEFINITIONS (SERVER-SIDE ONLY) ========================

PLANS = {
    "free": {
        "name": "Free",
        "price": 0.0,
        "currency": "usd",
        "max_monitors": 3,
        "max_users": 2,
        "max_servers": 5,
        "max_ai_runs": 50,
        "features": ["basic_monitoring", "email_alerts"],
        "interval": "month",
    },
    "pro": {
        "name": "Pro",
        "price": 49.00,
        "currency": "usd",
        "max_monitors": 50,
        "max_users": 10,
        "max_servers": 100,
        "max_ai_runs": 2000,
        "features": ["basic_monitoring", "email_alerts", "multi_region", "webhook_alerts", "query_analyzer", "attack_sim"],
        "interval": "month",
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 199.00,
        "currency": "usd",
        "max_monitors": 500,
        "max_users": 100,
        "max_servers": 1000,
        "max_ai_runs": 10000,
        "features": ["basic_monitoring", "email_alerts", "multi_region", "webhook_alerts", "query_analyzer", "attack_sim", "rbac", "soc_feed", "aws_connectors", "kafka", "ueba", "sla_reports"],
        "interval": "month",
    },
}

COST_PER_AI_RUN = 0.002


class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str


class CheckStatusRequest(BaseModel):
    session_id: str


# ======================== ENDPOINTS ========================

async def _get_plan(plan_id: str) -> Optional[dict]:
    """Lookup a plan from the DB first, falling back to the hardcoded constants."""
    if not plan_id:
        return None
    p = await db.plans.find_one({"id": plan_id, "is_active": True}, {"_id": 0})
    if p:
        return p
    return PLANS.get(plan_id)


@router.get("/plans")
async def list_plans(current_user: dict = Depends(require_auth)):
    """Get available billing plans — DB-backed with hardcoded fallback."""
    cursor = db.plans.find({"is_active": True}, {"_id": 0}).sort("sort_order", 1)
    db_plans = await cursor.to_list(length=50)
    if db_plans:
        return db_plans
    return [{"id": k, **v} for k, v in PLANS.items()]


@router.get("/current")
async def get_current_plan(current_user: dict = Depends(require_auth)):
    """Get current user's billing info"""
    user_id = current_user.get("id", "")
    tenant_id = current_user.get("tenant_id", "")

    sub = await db.subscriptions.find_one(
        {"$or": [{"user_id": user_id}, {"tenant_id": tenant_id}], "status": "active"},
        {"_id": 0}
    )
    if not sub:
        plan = await _get_plan("free") or PLANS["free"]
        return {
            "plan_id": "free",
            "plan": plan,
            "status": "active",
            "subscription": None,
        }

    plan_id = sub.get("plan_id", "free")
    plan = await _get_plan(plan_id) or PLANS.get(plan_id) or PLANS["free"]
    return {
        "plan_id": plan_id,
        "plan": plan,
        "status": sub.get("status", "active"),
        "subscription": sub,
    }


@router.post("/checkout")
async def create_checkout(req: CheckoutRequest, request: Request, current_user: dict = Depends(require_auth)):
    """Create a Stripe checkout session for a plan upgrade"""
    plan = await _get_plan(req.plan_id)
    if not plan:
        raise HTTPException(400, "Invalid plan")
    price = float(plan.get("price") or 0)
    if price <= 0:
        raise HTTPException(400, "Free / enterprise plans don't require checkout")
    if (plan.get("billing_type") or "").lower() == "enterprise":
        raise HTTPException(400, "Enterprise plans require a contact form submission")

    api_key = os.environ.get("STRIPE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "Stripe not configured")

    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)

    success_url = f"{req.origin_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{req.origin_url}/billing"

    metadata = {
        "plan_id": req.plan_id,
        "user_id": current_user.get("id", ""),
        "user_email": current_user.get("email", ""),
        "tenant_id": current_user.get("tenant_id", ""),
    }

    checkout_req = CheckoutSessionRequest(
        amount=price,
        currency=(plan.get("currency") or "usd").lower(),
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )

    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Record pending transaction
    tx = {
        "id": session.session_id,
        "session_id": session.session_id,
        "user_id": current_user.get("id", ""),
        "user_email": current_user.get("email", ""),
        "tenant_id": current_user.get("tenant_id", ""),
        "plan_id": req.plan_id,
        "amount": price,
        "currency": (plan.get("currency") or "usd").lower(),
        "payment_status": "initiated",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(tx)

    return {"url": session.url, "session_id": session.session_id}


@router.get("/checkout/status/{session_id}")
async def check_status(session_id: str, current_user: dict = Depends(require_auth)):
    """Check payment status and activate subscription if paid"""
    api_key = os.environ.get("STRIPE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "Stripe not configured")

    from emergentintegrations.payments.stripe.checkout import StripeCheckout

    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    status = await stripe_checkout.get_checkout_status(session_id)

    # Update transaction
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if tx and tx.get("payment_status") != "paid":
        new_status = status.payment_status
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": new_status,
                "status": "completed" if new_status == "paid" else "pending",
                "amount_total": status.amount_total,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        # Activate subscription on success
        if new_status == "paid" and tx.get("plan_id"):
            await _activate_subscription(tx)

    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
    }


@router.get("/transactions")
async def list_transactions(
    limit: int = 20,
    current_user: dict = Depends(require_auth),
):
    """Get payment transaction history"""
    user_id = current_user.get("id", "")
    txns = await db.payment_transactions.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return txns


@router.post("/downgrade")
async def downgrade_to_free(current_user: dict = Depends(require_auth)):
    """Downgrade to free plan"""
    user_id = current_user.get("id", "")
    await db.subscriptions.update_many(
        {"user_id": user_id, "status": "active"},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Downgraded to Free plan", "plan_id": "free"}


# ======================== WEBHOOK ========================

async def handle_stripe_webhook(request: Request):
    """Handle Stripe webhook events.

    Security model:
      1. Reads the Stripe-Signature header.
      2. Verifies the signature via emergentintegrations' StripeCheckout.handle_webhook
         (which internally uses the webhook secret to validate using HMAC SHA-256).
      3. If signature verification fails (raised as exception), returns 400 so the
         Stripe dashboard surfaces the failure rather than silently swallowing it.
      4. Idempotency: every processed event_id is recorded in `stripe_webhook_events`
         so retried deliveries don't double-activate subscriptions.
    """
    try:
        body = await request.body()
        api_key = os.environ.get("STRIPE_API_KEY", "")
        if not api_key:
            return {"status": "skipped", "reason": "STRIPE_API_KEY not configured"}

        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        sig = request.headers.get("Stripe-Signature", "")
        if not sig:
            raise HTTPException(400, "Missing Stripe-Signature header")
        # Production check — log if secret missing so ops can see it
        if not webhook_secret:
            logger.warning(
                "STRIPE_WEBHOOK_SECRET not set — signature verification depends on "
                "STRIPE_API_KEY (test mode). Set STRIPE_WEBHOOK_SECRET for production."
            )

        from emergentintegrations.payments.stripe.checkout import StripeCheckout

        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
        try:
            event = await stripe_checkout.handle_webhook(body, sig)
        except Exception as sig_err:
            # Signature verification failure — return 400 so Stripe surfaces the error
            logger.error("Stripe webhook signature verification failed: %s", sig_err)
            raise HTTPException(400, f"Signature verification failed: {sig_err}")

        # Idempotency: skip if we've already processed this event
        event_id = getattr(event, "event_id", None) or getattr(event, "id", None) or ""
        if event_id:
            existing = await db.stripe_webhook_events.find_one({"event_id": event_id}, {"_id": 0})
            if existing:
                logger.info("Stripe webhook %s already processed — skipping", event_id)
                return {"status": "ok", "duplicate": True, "event_id": event_id}
            await db.stripe_webhook_events.insert_one({
                "event_id": event_id,
                "event_type": event.event_type,
                "received_at": datetime.now(timezone.utc).isoformat(),
            })

        if event.payment_status == "paid":
            tx = await db.payment_transactions.find_one({"session_id": event.session_id}, {"_id": 0})
            if tx and tx.get("payment_status") != "paid":
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                await _activate_subscription(tx)

        return {"status": "ok", "event_type": event.event_type, "event_id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Return 500 (not 200) so Stripe will retry on transient backend failures
        raise HTTPException(500, str(e))


async def _activate_subscription(tx: dict):
    """Activate or update a subscription"""
    plan_id = tx.get("plan_id", "free")
    plan = PLANS.get(plan_id, PLANS["free"])

    sub = {
        "user_id": tx.get("user_id", ""),
        "user_email": tx.get("user_email", ""),
        "tenant_id": tx.get("tenant_id", ""),
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "status": "active",
        "max_monitors": plan["max_monitors"],
        "max_users": plan["max_users"],
        "max_servers": plan["max_servers"],
        "features": plan["features"],
        "session_id": tx.get("session_id", ""),
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Deactivate old subscriptions
    await db.subscriptions.update_many(
        {"user_id": tx.get("user_id"), "status": "active"},
        {"$set": {"status": "superseded"}}
    )
    await db.subscriptions.insert_one(sub)
    logger.info(f"Subscription activated: {tx.get('user_email')} -> {plan_id}")



# ======================== USAGE TRACKING ========================

@router.get("/usage")
async def get_usage(current_user: dict = Depends(require_auth)):
    """Get AI usage stats for current billing period"""
    user_id = current_user.get("id", "")
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    ai_runs = await db.ai_analyses.count_documents({
        "timestamp": {"$gte": period_start},
    })

    # Get current plan limits
    sub = await db.subscriptions.find_one(
        {"user_id": user_id, "status": "active"}, {"_id": 0}
    )
    plan_id = sub.get("plan_id", "free") if sub else "free"
    plan = PLANS.get(plan_id, PLANS["free"])
    limit = plan.get("max_ai_runs", 50)

    overage = max(0, ai_runs - limit)
    overage_cost = round(overage * COST_PER_AI_RUN, 2)

    return {
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "ai_runs_used": ai_runs,
        "ai_runs_limit": limit,
        "ai_runs_remaining": max(0, limit - ai_runs),
        "usage_pct": round((ai_runs / max(limit, 1)) * 100, 1),
        "overage_runs": overage,
        "overage_cost": overage_cost,
        "cost_per_run": COST_PER_AI_RUN,
        "period_start": period_start,
    }


@router.get("/analytics")
async def get_analytics(current_user: dict = Depends(require_auth)):
    """Get billing analytics: daily usage trend, cost breakdown, projections"""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Daily usage for current month
    daily_usage = []
    for day_offset in range(now.day):
        day_start = period_start.replace(day=day_offset + 1)
        day_end = day_start.replace(hour=23, minute=59, second=59)
        if day_end > now:
            day_end = now
        count = await db.ai_analyses.count_documents({
            "timestamp": {"$gte": day_start.isoformat(), "$lte": day_end.isoformat()},
        })
        daily_usage.append({
            "date": day_start.strftime("%b %d"),
            "day": day_start.day,
            "ai_runs": count,
            "cost": round(count * COST_PER_AI_RUN, 3),
        })

    # Agent breakdown
    agent_breakdown = []
    for aid in ["rca", "summarizer", "healer"]:
        count = await db.ai_analyses.count_documents({
            "agent_id": aid,
            "timestamp": {"$gte": period_start.isoformat()},
        })
        agent_breakdown.append({"agent": aid, "runs": count, "cost": round(count * COST_PER_AI_RUN, 3)})

    # Projections
    days_elapsed = max(now.day, 1)
    total_runs = sum(d["ai_runs"] for d in daily_usage)
    avg_daily = total_runs / days_elapsed
    days_in_month = 30
    projected_runs = round(avg_daily * days_in_month)
    projected_cost = round(projected_runs * COST_PER_AI_RUN, 2)

    # Get plan
    user_id = current_user.get("id", "")
    sub = await db.subscriptions.find_one({"user_id": user_id, "status": "active"}, {"_id": 0})
    plan_id = sub.get("plan_id", "free") if sub else "free"
    plan = PLANS.get(plan_id, PLANS["free"])
    plan_cost = plan["price"]

    return {
        "daily_usage": daily_usage,
        "agent_breakdown": agent_breakdown,
        "total_runs_this_month": total_runs,
        "avg_daily_runs": round(avg_daily, 1),
        "projected_monthly_runs": projected_runs,
        "projected_monthly_cost": projected_cost,
        "plan_cost": plan_cost,
        "estimated_total_bill": round(plan_cost + max(0, (projected_runs - plan.get("max_ai_runs", 50)) * COST_PER_AI_RUN), 2),
        "avg_tokens_per_run": 850,
        "cost_per_run": COST_PER_AI_RUN,
    }
