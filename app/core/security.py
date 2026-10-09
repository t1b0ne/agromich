import logging
from hmac import compare_digest

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Protección opcional: en producción defina AGROMICH_API_KEY."""
    expected = get_settings()["api_key"]
    if expected and not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key requerida")
    if expected and not compare_digest(x_api_key or "", expected):
        logger.warning("Intento de acceso con API key inválida")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key inválida")
