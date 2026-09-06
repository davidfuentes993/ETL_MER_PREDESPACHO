#!/usr/bin/env python
"""Punto de entrada del pipeline de Predespacho Regional del MER.

Uso:
    # Carga diaria (por defecto: mañana)
    python main.py --mode daily

    # Carga diaria con fecha explícita
    python main.py --mode daily --date 2026-09-10

    # Backfill de un rango de fechas
    python main.py --mode backfill --start-date 2019-01-01 --end-date 2019-01-31

Todos los parámetros de infraestructura (rutas, credenciales, endpoints del
portal) se resuelven vía variables de entorno / archivo .env a través de
Settings.load().
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from src.config.settings import ConfigError, Settings
from src.db.postgres_repository import PostgresRepository
from src.extractor.eor_client import EORClient
from src.extractor.fid_resolver import FidResolver
from src.orchestration.pipeline import PredespachoPipeline
from src.processing.bronze_writer import BronzeWriter
from src.processing.gold_builder import GoldBuilder
from src.processing.silver_transformer import SilverTransformer
from src.processing.zip_processor import ZipProcessor
from src.utils.logger import build_logger


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Fecha inválida '{value}', formato esperado YYYY-MM-DD"
        ) from exc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ETL de Predespacho Regional del MER (EOR) hacia PostgreSQL."
    )
    parser.add_argument(
        "--mode",
        choices=["daily", "backfill"],
        required=True,
        help="Modo de ejecución: 'daily' para una fecha puntual, 'backfill' para un rango.",
    )
    parser.add_argument(
        "--date",
        type=parse_date,
        default=None,
        help="Fecha a procesar en modo 'daily' (YYYY-MM-DD). Default: mañana.",
    )
    parser.add_argument(
        "--start-date",
        type=parse_date,
        default=None,
        help="Fecha inicial (inclusive) para modo 'backfill' (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=parse_date,
        default=None,
        help="Fecha final (inclusive) para modo 'backfill' (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Ruta a un archivo .env alternativo (opcional).",
    )
    return parser


def build_pipeline(settings: Settings, logger) -> PredespachoPipeline:
    """Construye el grafo de dependencias del pipeline (composition root)."""
    fid_resolver = FidResolver(
        fid_reciente=settings.eor_fid_reciente,
        fid_historico=settings.eor_fid_historico,
        cutoff_date=settings.eor_fid_cutoff_date,
    )
    eor_client = EORClient(
        base_url=settings.eor_base_url,
        volume_id=settings.eor_volume_id,
        report_prefix=settings.eor_report_prefix,
        fid_resolver=fid_resolver,
        timeout=settings.eor_request_timeout,
        logger=logger,
    )
    zip_processor = ZipProcessor(country_codes=settings.eor_country_codes, logger=logger)
    bronze_writer = BronzeWriter(settings.bronze_path, logger=logger)
    silver_transformer = SilverTransformer(
        settings.silver_path, header_row=settings.eor_header_row, logger=logger
    )
    repository = PostgresRepository(settings.db_dsn, logger=logger)
    repository.ensure_schema()
    gold_builder = GoldBuilder(repository, logger=logger)

    return PredespachoPipeline(
        eor_client=eor_client,
        zip_processor=zip_processor,
        bronze_writer=bronze_writer,
        silver_transformer=silver_transformer,
        gold_builder=gold_builder,
        repository=repository,
        logger=logger,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        settings = Settings.load(dotenv_path=args.env_file)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 1

    logger = build_logger("predespacho_etl", settings.log_path)

    try:
        pipeline = build_pipeline(settings, logger)
    except Exception as exc:
        logger.critical("No se pudo inicializar el pipeline: %s", exc)
        return 1

    if args.mode == "daily":
        target_date = args.date or (date.today() + timedelta(days=1))
        result = pipeline.run_for_date(target_date)
        if not result.exito:
            logger.error("Carga diaria fallida para %s: %s", target_date, result.error)
            return 1
        return 0

    # mode == "backfill"
    if not args.start_date or not args.end_date:
        logger.critical("El modo 'backfill' requiere --start-date y --end-date.")
        return 1
    if args.start_date > args.end_date:
        logger.critical("--start-date no puede ser posterior a --end-date.")
        return 1

    summary = pipeline.run_backfill(args.start_date, args.end_date)
    return 0 if summary.fallidas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())