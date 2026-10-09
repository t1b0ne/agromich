from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ReporteGenerado(BaseModel):
    archivo: str
    formato: Literal["html", "pdf"]
    tamano_bytes: int
    creado_en: datetime
