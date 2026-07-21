"""Routes: /threads, /threads/{id}/messages, /agent/run — Copilot chat."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from db import get_db
from deps import require_api_key
from models import ChatThread, ChatMessage, SendMessageIn
from agent.loop import run_agent

router = APIRouter(tags=["copilot"], dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


class ThreadCreate(BaseModel):
    title: Optional[str] = None
    skill_id: Optional[str] = None


class ThreadRename(BaseModel):
    title: str


@router.get("/threads", response_model=List[ChatThread],
            summary="List chat threads (recent first).")
async def list_threads(limit: int = 100):
    docs = await get_db().chat_threads.find({}, {"_id": 0}) \
        .sort("updated_at", -1).limit(limit).to_list(limit)
    return docs


@router.post("/threads", response_model=ChatThread, status_code=201,
             summary="Create a new chat thread.")
async def create_thread(payload: ThreadCreate):
    t = ChatThread(title=payload.title or "Nueva conversación",
                   skill_id=payload.skill_id)
    await get_db().chat_threads.insert_one(t.model_dump())
    return t


@router.patch("/threads/{thread_id}", response_model=ChatThread,
              summary="Rename a thread.")
async def rename_thread(thread_id: str, payload: ThreadRename):
    doc = await get_db().chat_threads.find_one_and_update(
        {"id": thread_id},
        {"$set": {"title": payload.title, "updated_at": _now()}},
        return_document=True, projection={"_id": 0})
    if not doc:
        raise HTTPException(404, "Thread not found")
    return doc


@router.delete("/threads/{thread_id}", summary="Delete a thread and its messages.")
async def delete_thread(thread_id: str):
    db = get_db()
    await db.chat_messages.delete_many({"thread_id": thread_id})
    r = await db.chat_threads.delete_one({"id": thread_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Thread not found")
    return {"ok": True}


@router.get("/threads/{thread_id}/messages", response_model=List[ChatMessage],
            summary="List messages in a thread.")
async def list_messages(thread_id: str):
    docs = await get_db().chat_messages.find({"thread_id": thread_id}, {"_id": 0}) \
        .sort("created_at", 1).to_list(500)
    return docs


@router.post("/agent/run",
             summary="Send a user message to the Copilot; runs the agent loop and returns steps + final answer.")
async def run(payload: SendMessageIn):
    db = get_db()

    # Ensure thread
    tid = payload.thread_id
    if not tid:
        t = ChatThread(title=(payload.text[:60] or "Nueva conversación"),
                       skill_id=payload.skill_id, auto_mode=payload.auto_mode)
        await db.chat_threads.insert_one(t.model_dump())
        tid = t.id

    # Persist user message
    user_msg = ChatMessage(thread_id=tid, role="user", content=payload.text)
    await db.chat_messages.insert_one(user_msg.model_dump())

    # Build history for the agent
    hist_docs = await db.chat_messages.find({"thread_id": tid, "role": {"$in": ["user", "assistant"]}},
                                            {"_id": 0}) \
        .sort("created_at", 1).to_list(500)
    history = [{"role": h["role"], "content": h["content"]} for h in hist_docs[:-1]]

    # Load skill if any
    skill_instructions = ""
    if payload.skill_id:
        s = await db.copilot_skills.find_one({"id": payload.skill_id}, {"_id": 0})
        if s:
            skill_instructions = s.get("instructions", "")

    # Run
    result = await run_agent(session_id=tid, history=history, user_text=payload.text,
                             skill_instructions=skill_instructions,
                             auto_mode=payload.auto_mode)

    # Persist assistant message with tool_calls trace
    tool_calls = []
    for step in result.get("steps", []):
        for tc in step.get("tool_calls", []) or []:
            tool_calls.append(tc)
    asst = ChatMessage(thread_id=tid, role="assistant",
                       content=result.get("final_text", ""),
                       tool_calls=tool_calls)
    await db.chat_messages.insert_one(asst.model_dump())
    await db.chat_threads.update_one({"id": tid}, {"$set": {"updated_at": _now()}})

    return {"thread_id": tid,
            "final_text": result.get("final_text", ""),
            "steps": result.get("steps", []),
            "message_id": asst.id}
