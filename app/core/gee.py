"""Inicialización única y perezosa de Google Earth Engine."""
import json
import os
import threading

import ee
from google.oauth2.credentials import Credentials

from app.core.config import get_settings

_lock = threading.Lock()
_initialized = False


def get_ee():
    """Devuelve EE inicializado; evita efectos secundarios al importar servicios."""
    global _initialized
    if _initialized:
        return ee
    with _lock:
        if _initialized:
            return ee
        settings = get_settings()
        credentials_json = os.getenv("EARTHENGINE_CREDENTIALS")
        try:
            if credentials_json:
                values = json.loads(credentials_json)
                credentials = Credentials(token=None, refresh_token=values.get("refresh_token"), client_id=values.get("client_id"), client_secret=values.get("client_secret"), token_uri=values.get("token_uri"), scopes=values.get("scopes"))
                ee.Initialize(credentials=credentials, project=values.get("project") or settings["earthengine_project"])
            else:
                ee.Initialize(project=settings["earthengine_project"])
        except Exception as exc:
            raise RuntimeError("Google Earth Engine no está disponible o no está configurado.") from exc
        _initialized = True
    return ee
