"""Configuración centralizada de logging para todo el pipeline."""
from __future__ import annotations

import logging
from pathlib import Path


def build_logger(name: str, log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """Crea (o reutiliza) un logger con salida a consola y a archivo.

    Se usa un único formato en toda la aplicación para que los logs de
    distintas clases sean fáciles de correlacionar durante una corrida.
    """
    logger = logging.getLogger(name)

    # Evita handlers duplicados si build_logger se llama varias veces
    # con el mismo nombre (por ejemplo, en tests).
    if logger.handlers:
        return logger

    logger.setLevel(level)

    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
