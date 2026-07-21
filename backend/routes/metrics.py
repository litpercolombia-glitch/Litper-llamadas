"""Routes: /metrics — dashboard KPIs."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends

from db import get_db
from deps import require_api_key

router = APIRouter(prefix="/metrics", tags=["metrics"],
                   dependencies=[Depends(require_api_key)])


@router.get("", summary="Aggregated KPIs for the dashboard.")
async def metrics():
    db = get_db()
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()

    # Queue counts by status
    queue_by_status: dict[str, int] = {}
    async for doc in db.call_queue.aggregate([
        {"$group": {"_id": "$status", "n": {"$sum": 1}}}
    ]):
        queue_by_status[doc["_id"] or "unknown"] = doc["n"]

    # Attempts today
    total_attempts_today = 0
    completed_today = 0
    contact_ok = 0
    async for sched in db.call_schedules.find({}, {"_id": 0, "attempts": 1}):
        for a in sched["attempts"]:
            ex = a.get("executed_at")
            if ex and ex >= since:
                total_attempts_today += 1
                if a.get("status") == "done":
                    completed_today += 1
                    if a.get("result") in ("confirmado", "ya_recogio", "extension"):
                        contact_ok += 1

    contact_rate = round((contact_ok / completed_today) * 100, 1) if completed_today else 0.0

    open_tasks = await db.customer_tasks.count_documents({"status": {"$in": ["open", "in_progress"]}})
    messages_24h = await db.message_log.count_documents({"created_at": {"$gte": since}})
    orders_total = await db.orders.count_documents({})
    queue_total = await db.call_queue.count_documents({})

    return {
        "queue_by_status": queue_by_status,
        "queue_total": queue_total,
        "orders_total": orders_total,
        "attempts_today": total_attempts_today,
        "completed_today": completed_today,
        "contact_rate_pct": contact_rate,
        "tasks_open": open_tasks,
        "messages_24h": messages_24h,
        "generated_at": now.isoformat(),
    }
