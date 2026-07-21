"""Shared FastAPI dependencies."""
import os
from fastapi import Header, HTTPException, status


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Validate X-API-Key header against PUBLIC_API_KEY env var."""
    expected = os.environ.get("PUBLIC_API_KEY")
    if not expected:
        # Fail closed if not configured
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="PUBLIC_API_KEY not configured on server")
    if x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing X-API-Key")
    return True
