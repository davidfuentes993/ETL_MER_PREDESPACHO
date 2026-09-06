"""Capa Bronze: persiste el dato crudo tal cual se descarga, con trazabilidad.

Convención de particionado en disco:

    {bronze_path}/fecha={YYYY-MM-DD}/pais={OSO00X}/
        ├── <archivo_excel_original>.xlsx
        └── _metadata.json

No se aplica ninguna transformación de contenido en esta capa: el objetivo
es preservar el archivo origen exactamente como llegó, junto con la
información necesaria para auditar de dónde vino cada dato.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BronzeRecord:
    """Referencia a un archivo ya persistido en la capa Bronze."""

    fecha_reporte: date
    pais_codigo: str
    excel_path: Path
    metadata_path: Path


class BronzeWriter:
    """Escribe archivos crudos y su metadata de trazabilidad en la capa Bronze."""

    def __init__(self, bronze_root: Path, logger=None) -> None:
        self._bronze_root = bronze_root
        self._logger = logger

    def write(
        self,
        fecha_reporte: date,
        pais_codigo: str,
        excel_path: Path,
        source_url: str,
    ) -> BronzeRecord:
        """Copia el Excel crudo a Bronze y escribe su metadata.

        Args:
            fecha_reporte: fecha del reporte de Predespacho (no la fecha de
                carga/ejecución).
            pais_codigo: código OSO00X detectado para este archivo.
            excel_path: ruta local del Excel ya extraído del ZIP.
            source_url: URL exacta desde la que se descargó el ZIP origen,
                para trazabilidad completa.
        """
        target_dir = (
            self._bronze_root
            / f"fecha={fecha_reporte:%Y-%m-%d}"
            / f"pais={pais_codigo}"
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        target_excel_path = target_dir / excel_path.name
        shutil.copy2(excel_path, target_excel_path)

        metadata = {
            "fecha_reporte": fecha_reporte.isoformat(),
            "pais_codigo": pais_codigo,
            "archivo_origen": excel_path.name,
            "source_url": source_url,
            "fecha_carga_utc": datetime.now(timezone.utc).isoformat(),
        }
        metadata_path = target_dir / "_metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if self._logger:
            self._logger.info(
                "Bronze OK fecha=%s pais=%s -> %s",
                fecha_reporte,
                pais_codigo,
                target_excel_path,
            )

        return BronzeRecord(
            fecha_reporte=fecha_reporte,
            pais_codigo=pais_codigo,
            excel_path=target_excel_path,
            metadata_path=metadata_path,
        )

    