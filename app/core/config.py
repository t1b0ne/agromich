import os
from functools import lru_cache

from dotenv import load_dotenv


@lru_cache
def get_settings() -> dict[str, str | None]:
    """Carga una vez la configuración no secreta del proceso."""
    load_dotenv()
    return {
        "earthengine_project": os.getenv("EARTHENGINE_PROJECT", "agromich-507422"),
        "api_key": os.getenv("AGROMICH_API_KEY"),
    }
