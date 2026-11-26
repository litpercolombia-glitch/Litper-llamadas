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
