"""Routes: /translate — real-time translation es|en|pt."""
from fastapi import APIRouter, Depends, HTTPException

from deps import require_api_key
from models import TranslateRequest, TranslateResponse
from translation import get_provider

router = APIRouter(prefix="/translate", tags=["translation"],
                   dependencies=[Depends(require_api_key)])


@router.post("", response_model=TranslateResponse,
             summary="Translate a piece of text between es/en/pt.")
async def translate(payload: TranslateRequest):
    if payload.target not in {"es", "en", "pt"}:
        raise HTTPException(400, "target must be es|en|pt")
    prov = get_provider()
    try:
        out = prov.translate(payload.text, payload.source, payload.target)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Translation failed: {e}")
    return TranslateResponse(text=out, source=payload.source,
                             target=payload.target, provider=prov.name)
