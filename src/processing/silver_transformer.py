"""Capa Silver: lectura, limpieza, tipado y homologación entre países.

Estructura Excel del EOR:
  * Cada hoja trae un bloque de membrete (título, logo, fecha de
    predespacho) antes de los datos reales; el encabezado real vive en la
    fila configurada por EOR_HEADER_ROW (confirmado: fila 7).
  * Además del membrete, quedan columnas en blanco a la izquierda
    ("Unnamed: 0", a veces también "Unnamed: 1") que se descartan.
  * La columna "Periodo" es la hora del día (0-23); se renombra a "hora"
    para alinearla con el resto del pipeline.
  * El grano real de TCP/TOP es por hora + nodo + agente + contrato (no
    solo por hora) — se preservan todas las columnas originales, sin
    agregación, para no perder esa granularidad de negocio.

Salida: un Parquet por (fecha, país, tipo_reporte) en:
    {silver_path}/tipo_reporte={TCP|TOP|PEXANTE}/fecha={YYYY-MM-DD}/pais={OSO00X}.parquet
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED_SHEETS = ("TCP", "TOP", "PEXANTE")

# Homologación de código de país del MER a nombre legible. Se deja como
# constante de código (no en .env) porque es conocimiento de negocio
# estable, distinto de los parámetros técnicos de integración con el EOR.
COUNTRY_NAME_MAP = {
    "OSO001": "Guatemala",
    "OSO002": "El Salvador",
    "OSO003": "Honduras",
    "OSO004": "Nicaragua",
    "OSO005": "Costa Rica",
    "OSO006": "Panamá",
}

# Renombres puntuales de columnas del EOR hacia nombres más claros para el
# resto del pipeline (aplicados después de la normalización a snake_case).
COLUMN_RENAMES = {
    "periodo": "hora",
}


class SilverTransformationError(Exception):
    """Se lanza cuando un archivo no puede transformarse (hoja faltante, etc.)."""


@dataclass(frozen=True)
class SilverOutput:
    tipo_reporte: str
    fecha_reporte: date
    pais_codigo: str
    parquet_path: Path
    filas: int


class SilverTransformer:
    """Transforma un Excel crudo (Bronze) en Parquet limpio y tipado (Silver)."""

    def __init__(self, silver_root: Path, header_row: int, logger=None) -> None:
        self._silver_root = silver_root
        self._header_row = header_row
        self._logger = logger

    def transform(
        self, excel_path: Path, fecha_reporte: date, pais_codigo: str
    ) -> list[SilverOutput]:
        """Lee las 3 hojas requeridas del Excel y las persiste como Parquet.

        Raises:
            SilverTransformationError: si falta alguna de las hojas
                requeridas o el archivo no puede leerse.
        """
        try:
            sheets = pd.read_excel(excel_path, sheet_name=None, header=self._header_row)
        except Exception as exc:
            raise SilverTransformationError(
                f"No se pudo leer {excel_path.name}: {exc}"
            ) from exc

        missing = [s for s in REQUIRED_SHEETS if s not in sheets]
        if missing:
            raise SilverTransformationError(
                f"{excel_path.name} no contiene las hojas requeridas: {missing} "
                f"(hojas encontradas: {list(sheets.keys())})"
            )

        outputs: list[SilverOutput] = []
        for tipo_reporte in REQUIRED_SHEETS:
            raw_df = sheets[tipo_reporte]
            clean_df = self._clean_dataframe(raw_df, fecha_reporte, pais_codigo, tipo_reporte)
            output = self._write_parquet(clean_df, tipo_reporte, fecha_reporte, pais_codigo)
            outputs.append(output)

        return outputs

    def _clean_dataframe(
        self,
        df: pd.DataFrame,
        fecha_reporte: date,
        pais_codigo: str,
        tipo_reporte: str,
    ) -> pd.DataFrame:
        clean = df.copy()
        clean.columns = [self._normalize_column(c) for c in clean.columns]

        # Descarta columnas "fantasma" (espaciado en blanco del template).
        clean = clean.loc[:, ~clean.columns.str.startswith("unnamed")]

        clean = clean.rename(columns=COLUMN_RENAMES)
        clean = clean.dropna(how="all")

        clean["fecha_reporte"] = pd.to_datetime(fecha_reporte)
        clean["pais_codigo"] = pais_codigo
        clean["pais_nombre"] = COUNTRY_NAME_MAP.get(pais_codigo, "Desconocido")
        clean["tipo_reporte"] = tipo_reporte

        if self._logger:
            self._logger.info(
                "Silver: %d filas limpiadas para pais=%s tipo=%s fecha=%s",
                len(clean),
                pais_codigo,
                tipo_reporte,
                fecha_reporte,
            )

        return clean

    def _write_parquet(
        self,
        df: pd.DataFrame,
        tipo_reporte: str,
        fecha_reporte: date,
        pais_codigo: str,
    ) -> SilverOutput:
        target_dir = (
            self._silver_root
            / f"tipo_reporte={tipo_reporte}"
            / f"fecha={fecha_reporte:%Y-%m-%d}"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"pais={pais_codigo}.parquet"

        df.to_parquet(target_path, index=False)

        return SilverOutput(
            tipo_reporte=tipo_reporte,
            fecha_reporte=fecha_reporte,
            pais_codigo=pais_codigo,
            parquet_path=target_path,
            filas=len(df),
        )

    @staticmethod
    def _normalize_column(column_name: object) -> str:
        text = str(column_name).strip()
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        return text.strip("_")