"""Descompresión recursiva de los ZIP de Predespacho.

Estructura  de un ZIP  descargado:

    PUB004-PRE-YYYYMMDD.zip                        (ZIP principal, 1 por fecha)
     ├── PUB004-PRE-YYYYMMDD-OSO001.zip             (ZIP anidado, 1 por país)
     │    └── PUB004-PRE-YYYYMMDD-OSO001-XXXXXX.xlsx (Excel; sufijo numérico variable
     │                                                 sin significado conocido, probablemente
     │                                                 hora de generación del reporte)
     ├── PUB004-PRE-YYYYMMDD-OSO002.zip
     ├── ...
     └── PUB004-PRE-YYYYMMDD-OSO006.zip

El nombre del ZIP anidado SÍ es predecible (mismo prefijo/fecha + código de
país). El nombre del Excel interno NO lo es completamente (trae un sufijo
variable) por lo que se localiza buscando cualquier .xlsx dentro de la
carpeta extraída, en vez de intentar predecir su nombre completo.

La lista de códigos de país válidos se recibe por constructor (viene de
Settings.eor_country_codes, configurable vía .env) en vez de estar quemada
en este módulo.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


class ZipProcessingError(Exception):
    """Se lanza cuando el ZIP principal está corrupto o no tiene ningún ZIP anidado."""


@dataclass(frozen=True)
class ExtractedCountryFile:
    """Representa un archivo Excel ya extraído, asociado a un país."""

    country_code: str  # ej. "OSO001"
    excel_path: Path
    source_zip_name: str


class ZipProcessor:
    """Descomprime el ZIP principal y cada ZIP anidado por país."""

    def __init__(self, country_codes: tuple[str, ...], logger=None) -> None:
        self._country_pattern = re.compile(
            "|".join(re.escape(code) for code in country_codes)
        )
        self._logger = logger

    def extract_all_countries(self, main_zip_path: Path, work_dir: Path) -> list[ExtractedCountryFile]:
        """Descomprime el ZIP principal y todos sus ZIP anidados por país.

        Args:
            main_zip_path: ruta al ZIP principal descargado (por fecha).
            work_dir: carpeta de trabajo donde extraer (se crea si no existe).

        Returns:
            Lista de archivos Excel extraídos, cada uno con su país detectado.
            Los países con estructura inesperada (sin .xlsx) se omiten con un
            log de error, no detienen el procesamiento de los demás.

        Raises:
            ZipProcessingError: si el ZIP principal está corrupto o no
                contiene ningún ZIP anidado reconocible.
        """
        work_dir.mkdir(parents=True, exist_ok=True)
        main_extract_dir = work_dir / "main"

        try:
            with zipfile.ZipFile(main_zip_path) as main_zip:
                main_zip.extractall(main_extract_dir)
        except zipfile.BadZipFile as exc:
            raise ZipProcessingError(
                f"El archivo {main_zip_path} no es un ZIP válido o está corrupto."
            ) from exc

        nested_zip_paths = list(main_extract_dir.rglob("*.zip"))
        if not nested_zip_paths:
            raise ZipProcessingError(
                f"El ZIP principal {main_zip_path.name} no contiene ningún "
                f"ZIP anidado por país; revisa si cambió la estructura del portal."
            )

        extracted_files: list[ExtractedCountryFile] = []
        for nested_zip_path in nested_zip_paths:
            country_code = self._detect_country_code(nested_zip_path.name)
            if not country_code:
                if self._logger:
                    self._logger.error(
                        "No se pudo determinar el país del ZIP anidado: %s",
                        nested_zip_path.name,
                    )
                continue

            country_extract_dir = work_dir / country_code
            try:
                with zipfile.ZipFile(nested_zip_path) as nested_zip:
                    nested_zip.extractall(country_extract_dir)
            except zipfile.BadZipFile:
                if self._logger:
                    self._logger.error(
                        "ZIP anidado corrupto, se omite: %s", nested_zip_path.name
                    )
                continue

            excel_paths = list(country_extract_dir.rglob("*.xlsx"))
            if not excel_paths:
                if self._logger:
                    self._logger.error(
                        "No se encontró ningún Excel dentro de %s (país=%s); se omite.",
                        nested_zip_path.name,
                        country_code,
                    )
                continue

            if len(excel_paths) > 1 and self._logger:
                self._logger.warning(
                    "Se encontró más de un .xlsx en %s (país=%s); se usará el primero: %s",
                    nested_zip_path.name,
                    country_code,
                    excel_paths[0].name,
                )

            extracted_files.append(
                ExtractedCountryFile(
                    country_code=country_code,
                    excel_path=excel_paths[0],
                    source_zip_name=nested_zip_path.name,
                )
            )

        return extracted_files

    def _detect_country_code(self, filename: str) -> str | None:
        match = self._country_pattern.search(filename.upper())
        return match.group(0) if match else None