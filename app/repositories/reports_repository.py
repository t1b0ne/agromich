import json
from pathlib import Path
from typing import Any

import pandas as pd


class ReportsRepository:
    """Persistencia local temporal de reportes, con rutas contenidas en reports/."""

    def __init__(self, root: str | Path = "reports"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str | Path) -> Path:
        destination = Path(path).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("La ruta del reporte debe permanecer dentro de reports")
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def write_json(self, path: str | Path, payload: Any) -> Path:
        destination = self._safe_path(path)
        with destination.open("w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2, default=str)
        return destination

    def write_dataframe(self, path: str | Path, dataframe: pd.DataFrame) -> Path:
        destination = self._safe_path(path)
        dataframe.to_csv(destination, index=False, encoding="utf-8-sig")
        return destination

    def write_text(self, path: str | Path, content: str) -> Path:
        destination = self._safe_path(path)
        destination.write_text(content, encoding="utf-8")
        return destination

    def write_bytes(self, path: str | Path, content: bytes) -> Path:
        destination = self._safe_path(path)
        destination.write_bytes(content)
        return destination

    def json_files(self, folders: list[str]) -> list[Path]:
        """Lista JSON existentes sin permitir salir de la raiz de reportes."""
        files: list[Path] = []
        for folder in folders:
            directory = self._safe_path(self.root / folder)
            if directory.exists() and directory.is_dir():
                files.extend(path for path in directory.rglob("*.json") if path.is_file())
        return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)

    @staticmethod
    def read_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)

    def generated_file(self, filename: str) -> Path:
        """Resuelve un reporte generado sin permitir traversal de directorios."""
        if Path(filename).name != filename or Path(filename).suffix.lower() not in {".html", ".pdf"}:
            raise ValueError("Nombre de reporte inválido")
        path = self._safe_path(self.root / "generados" / filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path

    def generated_files(self) -> list[Path]:
        directory = self._safe_path(self.root / "generados")
        if not directory.is_dir():
            return []
        return sorted(
            (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".html", ".pdf"}),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
