"""Routes: /tasks — CRUD for customer tasks/tickets."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from db import get_db
from deps import get_org, require_api_key
from models import Task, TaskIn, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"],
                   dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.post("", response_model=Task, status_code=201,
             summary="Create a customer task/ticket.")
async def create_task(payload: TaskIn, org: str = Depends(get_org)):
    task = Task(**payload.model_dump())
    await get_db().customer_tasks.insert_one({**task.model_dump(), "org_id": org})
    return task


@router.get("", response_model=List[Task],
            summary="List tasks.")
async def list_tasks(status: Optional[str] = None,
                     type: Optional[str] = None,
                     limit: int = 100,
                     org: str = Depends(get_org)):
    q = {"org_id": org}
    if status:
        q["status"] = status
    if type:
        q["type"] = type
    docs = await get_db().customer_tasks.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    return docs


@router.get("/{task_id}", response_model=Task,
            summary="Get a task.")
async def get_task(task_id: str, org: str = Depends(get_org)):
    doc = await get_db().customer_tasks.find_one({"id": task_id, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Task not found")
    return doc


@router.patch("/{task_id}", response_model=Task,
              summary="Update a task (status, description, assignee, due date, type).")
async def update_task(task_id: str, payload: TaskUpdate, org: str = Depends(get_org)):
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_at"] = _now()
    r = await get_db().customer_tasks.find_one_and_update(
        {"id": task_id, "org_id": org}, {"$set": upd},
        return_document=True, projection={"_id": 0})
    if not r:
        raise HTTPException(404, "Task not found")
    return r


@router.delete("/{task_id}", summary="Delete a task.")
async def delete_task(task_id: str, org: str = Depends(get_org)):
    r = await get_db().customer_tasks.delete_one({"id": task_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "Task not found")
    return {"ok": True, "id": task_id}
