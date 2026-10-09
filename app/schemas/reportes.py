from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator


class SolicitudReporte(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=150, description="Titulo principal del reporte")
    estado: str = Field(..., min_length=2, max_length=100, description="Estado obligatorio")
    municipio: str = Field(..., min_length=2, max_length=100, description="Municipio obligatorio")
    servicios: List[str] = Field(default_factory=list, max_length=4)
    incluir_historial: bool = False
    formato: Literal["html", "pdf"] = "html"
    datos_adicionales: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("servicios")
    @classmethod
    def validar_servicios(cls, values: List[str]) -> List[str]:
        permitidos = {"clima", "suelo", "sanidad", "procesados"}
        if not values:
            return sorted(permitidos)
        normalizados = [value.strip().lower() for value in values]
        invalidos = set(normalizados) - permitidos
        if invalidos:
            raise ValueError(f"Servicios no soportados: {', '.join(sorted(invalidos))}")
        return list(dict.fromkeys(normalizados))
