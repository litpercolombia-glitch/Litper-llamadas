"""Routes: /threads, /threads/{id}/messages, /agent/run (= /copilot/run),
/copilot/confirm, /copilot/activity — Copilot chat."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel

from db import get_db
from deps import get_ctx, get_org, require_api_key
from models import ChatThread, ChatMessage, SendMessageIn
from agent.loop import run_agent, resume_agent, supersede_pending, ActionError

router = APIRouter(tags=["copilot"], dependencies=[Depends(require_api_key)])

# Aislamiento: hilos y mensajes llevan org_id; listar, renombrar, borrar y leer
# filtran SIEMPRE por el org de la sesión (deps.get_org). El agente recibe
# ctx={"org_id","user_id"} vía run_agent(..., org_id=..., user_id=...).
# CONFIRMACIÓN HUMANA: si el agente pide una herramienta con efecto externo o
# costo, /copilot/run devuelve `pending_action {id, tool, resumen, args}` SIN
# ejecutarla; /copilot/confirm {action_id, approve} la ejecuta (una sola vez) o
# la descarta. Todas las rutas usan get_org/get_ctx: el org nunca sale del
# cuerpo ni de cabeceras.


def _now():
    return datetime.now(timezone.utc).isoformat()


class ThreadCreate(BaseModel):
    title: Optional[str] = None
    skill_id: Optional[str] = None


class ThreadRename(BaseModel):
    title: str


@router.get("/threads", response_model=List[ChatThread],
            summary="List chat threads (recent first).")
async def list_threads(limit: int = 100, org: str = Depends(get_org)):
    docs = await get_db().chat_threads.find({"org_id": org}, {"_id": 0}) \
        .sort("updated_at", -1).limit(limit).to_list(limit)
    return docs


@router.post("/threads", response_model=ChatThread, status_code=201,
             summary="Create a new chat thread.")
async def create_thread(payload: Optional[ThreadCreate] = None, org: str = Depends(get_org)):
    p = payload or ThreadCreate()
    t = ChatThread(title=p.title or "Nueva conversación",
                   skill_id=p.skill_id)
    await get_db().chat_threads.insert_one({**t.model_dump(), "org_id": org})
    return t


async def current_pending(org: str, thread_id: str) -> dict | None:
    """Acción del hilo que sigue esperando "Aplicar/Cancelar" (pendiente y sin
    vencer), tal como la muestra la tarjeta. None si no hay."""
    docs = await get_db().pending_actions.find(
        {"org_id": org, "thread_id": thread_id, "status": "pending"},
        {"_id": 0, "state": 0}).sort("created_at", -1).limit(1).to_list(1)
    if not docs or (docs[0].get("expires_at") or "") < _now():
        return None
    a = docs[0]
    return {"id": a["id"], "tool": a.get("tool"), "resumen": a.get("resumen"),
            "args": a.get("args") or {}, "expires_at": a.get("expires_at")}


@router.get("/copilot/threads/{thread_id}",
            summary="Un hilo + su acción pendiente vigente (para que la tarjeta de "
                    "confirmación sobreviva a recargar o a abrir en otro dispositivo).")
@router.get("/threads/{thread_id}", summary="Igual que /copilot/threads/{id}.")
async def get_thread(thread_id: str, org: str = Depends(get_org)):
    t = await get_db().chat_threads.find_one({"id": thread_id, "org_id": org}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Thread not found")
    t.pop("org_id", None)
    return {**t, "pending_action": await current_pending(org, thread_id)}


@router.patch("/threads/{thread_id}", response_model=ChatThread,
              summary="Rename a thread.")
async def rename_thread(thread_id: str, payload: ThreadRename, org: str = Depends(get_org)):
    doc = await get_db().chat_threads.find_one_and_update(
        {"id": thread_id, "org_id": org},
        {"$set": {"title": payload.title, "updated_at": _now()}},
        return_document=True, projection={"_id": 0})
    if not doc:
        raise HTTPException(404, "Thread not found")
    return doc


@router.delete("/threads/{thread_id}", summary="Delete a thread and its messages.")
async def delete_thread(thread_id: str, org: str = Depends(get_org)):
    db = get_db()
    # Primero el hilo (prueba de propiedad); solo entonces sus mensajes.
    r = await db.chat_threads.delete_one({"id": thread_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "Thread not found")
    await db.chat_messages.delete_many({"thread_id": thread_id, "org_id": org})
    return {"ok": True}


@router.get("/threads/{thread_id}/messages", response_model=List[ChatMessage],
            summary="List messages in a thread.")
async def list_messages(thread_id: str, org: str = Depends(get_org)):
    docs = await get_db().chat_messages.find(
        {"thread_id": thread_id, "org_id": org}, {"_id": 0}) \
        .sort("created_at", 1).to_list(500)
    return docs


@router.post("/copilot/run",
             summary="Envía un mensaje al asistente. Devuelve la respuesta y, si algo espera "
                     "confirmación, `pending_action` (sin ejecutarlo).")
@router.post("/agent/run",
             summary="Send a user message to the Copilot; runs the agent loop and returns steps + final answer.")
async def run(payload: SendMessageIn, request: Request):
    db = get_db()
    # Cliente (tenant) dueño de la llave de IA y de TODOS los datos del turno.
    ctx = get_ctx(request)
    org_id = ctx["org_id"]

    # Ensure thread. Un thread_id que no es de ESTE cliente se trata igual
    # exista o no en otro cliente (no se revela nada): se abre un hilo nuevo
    # con id generado por el servidor.
    tid = payload.thread_id
    if tid and not await db.chat_threads.find_one({"id": tid, "org_id": org_id}, {"_id": 0, "id": 1}):
        tid = None
    if not tid:
        t = ChatThread(title=(payload.text[:60] or "Nueva conversación"),
                       skill_id=payload.skill_id, auto_mode=payload.auto_mode)
        await db.chat_threads.insert_one({**t.model_dump(), "org_id": org_id})
        tid = t.id

    # Un mensaje nuevo invalida lo que estuviera esperando confirmación en el hilo.
    await supersede_pending(org_id, tid)

    # Persist user message
    user_msg = ChatMessage(thread_id=tid, role="user", content=payload.text)
    await db.chat_messages.insert_one({**user_msg.model_dump(), "org_id": org_id})

    # Build history for the agent
    hist_docs = await db.chat_messages.find({"thread_id": tid, "org_id": org_id,
                                             "role": {"$in": ["user", "assistant"]}},
                                            {"_id": 0}) \
        .sort("created_at", 1).to_list(500)
    history = [{"role": h["role"], "content": h["content"]} for h in hist_docs[:-1]]

    # Load skill if any
    skill_instructions = ""
    if payload.skill_id:
        s = await db.copilot_skills.find_one({"id": payload.skill_id, "org_id": org_id},
                                             {"_id": 0})
        if s:
            skill_instructions = s.get("instructions", "")

    # Run
    result = await run_agent(session_id=tid, history=history, user_text=payload.text,
                             skill_instructions=skill_instructions,
                             auto_mode=payload.auto_mode,
                             model_override=payload.model_override,
                             org_id=org_id, user_id=ctx["user_id"])

    # Persist assistant message with tool_calls trace
    tool_calls = []
    for step in result.get("steps", []):
        for tc in step.get("tool_calls", []) or []:
            tool_calls.append(tc)
    asst = ChatMessage(thread_id=tid, role="assistant",
                       content=result.get("final_text", ""),
                       tool_calls=tool_calls)
    asst_dict = asst.model_dump()
    asst_dict["provider"] = result.get("provider")
    asst_dict["org_id"] = org_id
    pending = result.get("pending_action")
    if pending:
        asst_dict["pending_action_id"] = pending["id"]
    await db.chat_messages.insert_one(asst_dict)
    await db.chat_threads.update_one({"id": tid, "org_id": org_id},
                                     {"$set": {"updated_at": _now()}})

    return {"thread_id": tid,
            "final_text": result.get("final_text", ""),
            "provider": result.get("provider"),
            "steps": result.get("steps", []),
            "tool_calls": tool_calls,
            "pending_action": pending,
            "message_id": asst.id}


class ConfirmIn(BaseModel):
    action_id: str
    approve: bool = False


@router.post("/copilot/confirm",
             summary="Aplica (approve=true) o cancela una acción propuesta por el asistente. "
                     "Se ejecuta UNA sola vez; vence a los 30 minutos.")
async def confirm(payload: ConfirmIn, request: Request):
    db = get_db()
    ctx = get_ctx(request)
    org_id = ctx["org_id"]
    try:
        r = await resume_agent(payload.action_id, bool(payload.approve),
                               org_id=org_id, user_id=ctx["user_id"])
    except ActionError as e:
        raise HTTPException(e.code, str(e))

    tid = r.get("thread_id")
    message_id = None
    if tid and await db.chat_threads.find_one({"id": tid, "org_id": org_id}, {"_id": 0, "id": 1}):
        action = await db.pending_actions.find_one(
            {"id": payload.action_id, "org_id": org_id}, {"_id": 0, "resumen": 1, "tool": 1}) or {}
        label = action.get("resumen") or action.get("tool") or "acción"
        decision = ChatMessage(thread_id=tid, role="user",
                               content=("Aplicar: " if payload.approve else "Cancelar: ") + label)
        await db.chat_messages.insert_one({**decision.model_dump(), "org_id": org_id})
        asst = ChatMessage(thread_id=tid, role="assistant", content=r.get("final_text", ""),
                           tool_calls=r.get("tool_calls") or [])
        d = asst.model_dump()
        d.update(provider=r.get("provider"), org_id=org_id)
        if r.get("pending_action"):
            d["pending_action_id"] = r["pending_action"]["id"]
        await db.chat_messages.insert_one(d)
        await db.chat_threads.update_one({"id": tid, "org_id": org_id},
                                         {"$set": {"updated_at": _now()}})
        message_id = asst.id
    return {"thread_id": tid, "action_id": payload.action_id, "status": r.get("status"),
            "final_text": r.get("final_text", ""), "provider": r.get("provider"),
            "steps": r.get("steps", []), "tool_calls": r.get("tool_calls") or [],
            "pending_action": r.get("pending_action"), "message_id": message_id}


@router.get("/copilot/activity",
            summary='Bitácora "Lo que hizo el asistente": últimas 50 herramientas usadas por este cliente.')
async def activity(limit: int = 50, org: str = Depends(get_org)):
    limit = max(1, min(int(limit or 50), 50))
    docs = await get_db().agent_tool_calls.find({"org_id": org}, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    items = [{"id": d.get("id"), "tool": d.get("tool") or d.get("action"),
              "kind": d.get("kind") or "agente_voz",
              "args": d.get("args") if d.get("args") is not None else d.get("payload") or {},
              "ok": d.get("ok", True), "ms": d.get("ms"), "error": d.get("error") or "",
              "confirmed": bool(d.get("confirmed")), "thread_id": d.get("thread_id"),
              "created_at": d.get("created_at")} for d in docs]
    return {"items": items, "count": len(items)}
