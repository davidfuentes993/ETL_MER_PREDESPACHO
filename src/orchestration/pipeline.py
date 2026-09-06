"""Orquestador end-to-end del pipeline de Predespacho.

Esta es la única clase que conoce el orden completo de las etapas; cada
etapa individual (extractor, zip processor, bronze, silver, gold) no sabe
nada de las demás. Un país con estructura inesperada no detiene el
procesamiento de los demás países de esa misma fecha; solo un fallo en la
descarga o descompresión del ZIP principal detiene la fecha completa.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from src.db.postgres_repository import PostgresRepository
from src.extractor.eor_client import EORClient
from src.extractor.exceptions import EORExtractionError
from src.processing.bronze_writer import BronzeWriter
from src.processing.gold_builder import GoldBuilder
from src.processing.silver_transformer import SilverTransformationError, SilverTransformer
from src.processing.zip_processor import ZipProcessingError, ZipProcessor


@dataclass
class DateResult:
    """Resultado de procesar una fecha individual."""

    fecha: date
    exito: bool
    paises_cargados: int = 0
    filas_insertadas: int = 0
    error: str | None = None


@dataclass
class BackfillSummary:
    """Resumen de una corrida de backfill sobre un rango de fechas."""

    resultados: list[DateResult] = field(default_factory=list)

    @property
    def exitosas(self) -> int:
        return sum(1 for r in self.resultados if r.exito)

    @property
    def fallidas(self) -> int:
        return sum(1 for r in self.resultados if not r.exito)


class PredespachoPipeline:
    """Encadena extracción, descompresión, Bronze, Silver y Gold para una fecha."""

    def __init__(
        self,
        eor_client: EORClient,
        zip_processor: ZipProcessor,
        bronze_writer: BronzeWriter,
        silver_transformer: SilverTransformer,
        gold_builder: GoldBuilder,
        repository: PostgresRepository,
        logger=None,
    ) -> None:
        self._eor_client = eor_client
        self._zip_processor = zip_processor
        self._bronze_writer = bronze_writer
        self._silver_transformer = silver_transformer
        self._gold_builder = gold_builder
        self._repository = repository
        self._logger = logger

    def run_for_date(self, fecha: date) -> DateResult:
        """Ejecuta el pipeline completo para una única fecha."""
        if self._logger:
            self._logger.info("=== Iniciando pipeline para fecha=%s ===", fecha)

        with tempfile.TemporaryDirectory(prefix=f"predespacho_{fecha:%Y%m%d}_") as tmp:
            tmp_dir = Path(tmp)
            try:
                zip_path = self._eor_client.download(fecha, tmp_dir)
                extracted_files = self._zip_processor.extract_all_countries(zip_path, tmp_dir)
            except (EORExtractionError, ZipProcessingError) as exc:
                self._repository.upsert_control_carga(fecha, "ERROR", 0, str(exc))
                if self._logger:
                    self._logger.error("Pipeline falló para fecha=%s: %s", fecha, exc)
                return DateResult(fecha=fecha, exito=False, error=str(exc))

            paises_cargados = 0
            filas_insertadas = 0

            for extracted in extracted_files:
                try:
                    bronze_record = self._bronze_writer.write(
                        fecha_reporte=fecha,
                        pais_codigo=extracted.country_code,
                        excel_path=extracted.excel_path,
                        source_url=self._eor_client.build_download_url(fecha),
                    )
                    silver_outputs = self._silver_transformer.transform(
                        bronze_record.excel_path, fecha, extracted.country_code
                    )
                    for silver_output in silver_outputs:
                        filas_insertadas += self._gold_builder.load_silver_output(silver_output)

                    paises_cargados += 1
                except SilverTransformationError as exc:
                    if self._logger:
                        self._logger.error(
                            "Fallo procesando pais=%s fecha=%s: %s",
                            extracted.country_code,
                            fecha,
                            exc,
                        )
                    continue

            estado = "OK" if paises_cargados == len(extracted_files) else "PARCIAL"
            self._repository.upsert_control_carga(fecha, estado, paises_cargados)

            if self._logger:
                self._logger.info(
                    "=== Pipeline %s fecha=%s paises=%d/%d filas=%d ===",
                    estado, fecha, paises_cargados, len(extracted_files), filas_insertadas,
                )

            return DateResult(
                fecha=fecha,
                exito=True,
                paises_cargados=paises_cargados,
                filas_insertadas=filas_insertadas,
            )

    def run_backfill(self, start_date: date, end_date: date, skip_loaded: bool = True) -> BackfillSummary:
        """Ejecuta el pipeline para cada fecha en [start_date, end_date]."""
        summary = BackfillSummary()
        current = start_date

        while current <= end_date:
            if skip_loaded and self._repository.fecha_ya_cargada(current):
                if self._logger:
                    self._logger.info("Fecha %s ya cargada, se omite.", current)
                current += timedelta(days=1)
                continue

            result = self.run_for_date(current)
            summary.resultados.append(result)
            current += timedelta(days=1)

        if self._logger:
            self._logger.info(
                "=== Backfill terminado: %d OK, %d fallidas de %d fechas ===",
                summary.exitosas, summary.fallidas, len(summary.resultados),
            )
        return summary