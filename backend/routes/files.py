"""Routes: /files — upload CSV/XLSX/PDF/images; parse tabular files."""
from datetime import datetime, timezone
import io
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from typing import List, Optional

from db import get_db
from deps import get_org, require_api_key
from models import UploadedFile

router = APIRouter(prefix="/files", tags=["copilot"],
                   dependencies=[Depends(require_api_key)])

MAX_PREVIEW_ROWS = 500  # cap on how much we keep in memory for agent import
MAX_BYTES = 15 * 1024 * 1024      # tope por archivo
MAX_IMAGEN = 4 * 1024 * 1024      # imágenes que el asistente puede ver
MAX_TEXTO = 40_000                # caracteres de texto que se guardan para el asistente
TEXTO_EXT = (".txt", ".md", ".json", ".log", ".tsv")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _detect_kind(filename: str, content_type: str) -> str:
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        return "csv"
    if fn.endswith((".xlsx", ".xls")):
        return "xlsx"
    if fn.endswith(".pdf"):
        return "pdf"
    if content_type and content_type.startswith("image/"):
        return "image"
    return "other"


def _parse_csv(data: bytes) -> tuple[list[dict], list[str], int]:
    import pandas as pd
    df = pd.read_csv(io.BytesIO(data))
    df = df.fillna("")
    total = len(df)
    preview = df.head(MAX_PREVIEW_ROWS).to_dict(orient="records")
    return preview, list(df.columns), total


def _parse_xlsx(data: bytes) -> tuple[list[dict], list[str], int]:
    import pandas as pd
    df = pd.read_excel(io.BytesIO(data), engine="openpyxl")
    df = df.fillna("")
    total = len(df)
    preview = df.head(MAX_PREVIEW_ROWS).to_dict(orient="records")
    return preview, list(df.columns), total


@router.post("", response_model=UploadedFile, status_code=201,
             summary="Upload a file (CSV/XLSX parsed automatically). Attaches to a thread if thread_id passed.")
async def upload(file: UploadFile = File(...),
                 thread_id: Optional[str] = Form(None),
                 org: str = Depends(get_org)):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "El archivo pesa más de 15 MB. Súbelo más liviano o por partes.")
    kind = _detect_kind(file.filename or "", file.content_type or "")
    columns: list[str] = []
    preview: list[dict] = []
    row_count = 0
    if kind == "csv":
        try:
            preview, columns, row_count = _parse_csv(data)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"CSV inválido: {e}")
    elif kind == "xlsx":
        try:
            preview, columns, row_count = _parse_xlsx(data)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"XLSX inválido: {e}")
    # Lo que el asistente podrá leer: imagen (para verla) o texto (PDF y archivos de texto).
    extra: dict = {}
    nombre = (file.filename or "").lower()
    if kind == "image" and len(data) <= MAX_IMAGEN:
        import base64
        extra["data_b64"] = base64.b64encode(data).decode()
    elif kind == "pdf":
        try:
            from pypdf import PdfReader
            paginas = PdfReader(io.BytesIO(data)).pages[:30]
            extra["texto"] = "\n".join((p.extract_text() or "") for p in paginas)[:MAX_TEXTO]
        except Exception:  # noqa: BLE001 — PDF escaneado o sin lector: se guarda sin texto
            pass
    elif nombre.endswith(TEXTO_EXT) or (file.content_type or "").startswith("text/"):
        extra["texto"] = data.decode("utf-8", errors="replace")[:MAX_TEXTO]

    doc = UploadedFile(
        id=str(uuid.uuid4()),
        filename=file.filename or "sin_nombre",
        content_type=file.content_type or "",
        size=len(data),
        kind=kind,  # type: ignore[arg-type]
        rows_preview=preview,
        columns=columns,
        row_count=row_count,
        thread_id=thread_id,
        created_at=_now(),
    )
    await get_db().uploaded_files.insert_one({**doc.model_dump(), **extra, "org_id": org})
    return doc


MAX_AUDIO = 25 * 1024 * 1024
SIN_VOZ = ("Para dictar o subir audios conecta ElevenLabs en Conexiones (la misma llave de los agentes de voz). "
           "También sirve una llave de Groq o de Gemini.")


async def _oir_elevenlabs(key: str, nombre: str, mime: str, data: bytes) -> str:
    import os
    import httpx
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key},
                           data={"model_id": os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v1")},
                           files={"file": (nombre, data, mime)})
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


async def _oir_groq(key: str, nombre: str, mime: str, data: bytes) -> str:
    import os
    import httpx
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post("https://api.groq.com/openai/v1/audio/transcriptions",
                           headers={"Authorization": f"Bearer {key}"},
                           data={"model": os.environ.get("GROQ_STT_MODEL", "whisper-large-v3")},
                           files={"file": (nombre, data, mime)})
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


async def _oir_gemini(key: str, nombre: str, mime: str, data: bytes) -> str:
    import base64
    import httpx
    from agent.router import PROVIDERS
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{PROVIDERS['gemini']['model']}:generateContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": [
                {"text": "Transcribe literalmente este audio en su idioma original. Devuelve solo el texto."},
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}]}]})
    r.raise_for_status()
    return (r.json()["candidates"][0]["content"]["parts"][0]["text"] or "").strip()


@router.post("/transcribir",
             summary="Pasa a texto un audio o video (dictado o archivo) con la llave de voz de ESTE cliente. "
                     "No guarda el audio.")
async def transcribir(file: UploadFile = File(...), org: str = Depends(get_org)):
    data = await file.read()
    mime = (file.content_type or "").split(";")[0].strip() or "audio/webm"
    if not mime.startswith(("audio/", "video/")):
        raise HTTPException(400, "Sube un audio o un video.")
    if not data:
        raise HTTPException(400, "El audio llegó vacío. Graba de nuevo.")
    if len(data) > MAX_AUDIO:
        raise HTTPException(413, "El audio pesa más de 25 MB. Córtalo en partes más cortas.")
    from agent.router import _safe_err
    from org_credentials import get_credentials
    intentado = False
    for proveedor, fn in (("elevenlabs", _oir_elevenlabs), ("groq", _oir_groq), ("gemini", _oir_gemini)):
        try:
            key = (await get_credentials(proveedor, org)).get("api_key", "")
        except Exception:  # noqa: BLE001
            key = ""
        if not key:
            continue
        intentado = True
        try:
            texto = await fn(key, file.filename or "audio.webm", mime, data)
            if texto:
                return {"texto": texto[:8000], "proveedor": proveedor}
        except Exception as e:  # noqa: BLE001 — sin secretos en el log
            import logging
            logging.getLogger("files").warning("Transcripción %s falló (org=%s): %s", proveedor, org, _safe_err(e, [key]))
    if not intentado:
        raise HTTPException(409, SIN_VOZ)
    raise HTTPException(502, "No pude entender el audio. Inténtalo de nuevo o escríbelo.")


@router.get("", response_model=List[UploadedFile],
            summary="List uploaded files.")
async def list_files(thread_id: Optional[str] = None, limit: int = 50,
                     org: str = Depends(get_org)):
    q = {"org_id": org}
    if thread_id:
        q["thread_id"] = thread_id
    docs = await get_db().uploaded_files.find(q,
        {"_id": 0, "rows_preview": 0, "data_b64": 0, "texto": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    # rows_preview stripped to keep responses small; use GET /files/{id} for full
    return docs


@router.get("/{file_id}", response_model=UploadedFile,
            summary="Get one file including preview rows.")
async def get_file(file_id: str, org: str = Depends(get_org)):
    doc = await get_db().uploaded_files.find_one({"id": file_id, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "File not found")
    return doc


@router.delete("/{file_id}", summary="Delete a file.")
async def delete_file(file_id: str, org: str = Depends(get_org)):
    r = await get_db().uploaded_files.delete_one({"id": file_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "File not found")
    return {"ok": True}
