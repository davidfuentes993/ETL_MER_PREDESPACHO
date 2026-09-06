"""Configuración centralizada de la aplicación.

Todos los valores sensibles o dependientes del entorno (rutas, credenciales,
parámetros del portal EOR) se resuelven aquí a partir de variables de
entorno. Ningún otro módulo debe leer `os.environ` directamente ni contener
valores quemados: si un componente necesita un parámetro, se lo debe pasar
una instancia de `Settings`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Se lanza cuando falta el .env, o falta/es inválida una variable requerida."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"La variable de entorno '{name}' es requerida y no fue definida "
            f"(revisa tu archivo .env)."
        )
    return value


def _optional(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    """Agrupa toda la configuración del pipeline, ya validada y tipada."""

    # --- Portal EOR ---
    eor_base_url: str
    eor_volume_id: str
    eor_fid_reciente: str
    eor_fid_historico: str
    eor_fid_cutoff_date: date
    eor_report_prefix: str
    eor_request_timeout: int
    eor_country_codes: tuple[str, ...]
    eor_header_row: int

    # --- Rutas locales (capas del medallón) ---
    bronze_path: Path
    silver_path: Path
    log_path: Path

    # --- Base de datos ---
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    @property
    def db_dsn(self) -> str:
        """Cadena de conexión SQLAlchemy hacia PostgreSQL."""
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @classmethod
    def load(cls, dotenv_path: str | None = None) -> "Settings":
        """Carga y valida la configuración desde el archivo .env."""

        env_file = Path(dotenv_path) if dotenv_path else Path(".env")
        if not env_file.exists():
            raise ConfigError(
                f"No se encontró el archivo de configuración '{env_file}'. "
                f"Copia .env.example a .env y completa los valores antes "
                f"de ejecutar el pipeline."
            )

        load_dotenv(dotenv_path=env_file, override=False)

        cutoff_raw = _optional("EOR_FID_CUTOFF_DATE", "2019-01-01")
        try:
            cutoff_date = datetime.strptime(cutoff_raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ConfigError(
                f"EOR_FID_CUTOFF_DATE debe tener formato YYYY-MM-DD, "
                f"se recibió: '{cutoff_raw}'"
            ) from exc

        country_codes_raw = _optional(
            "EOR_COUNTRY_CODES", "OSO001,OSO002,OSO003,OSO004,OSO005,OSO006"
        )
        country_codes = tuple(
                code.strip() for code in country_codes_raw.split(",") if code.strip()
        )

        return cls(
            eor_base_url=_optional("EOR_BASE_URL", "https://www.enteoperador.org/"),
            eor_volume_id=_optional("EOR_VOLUME_ID", "l1"),
            eor_fid_reciente=_require("EOR_FID_RECIENTE"),
            eor_fid_historico=_require("EOR_FID_HISTORICO"),
            eor_fid_cutoff_date=cutoff_date,
            eor_report_prefix=_optional("EOR_REPORT_PREFIX", "PUB004-PRE"),
            eor_request_timeout=int(_optional("EOR_REQUEST_TIMEOUT", "30")),
            bronze_path=Path(_optional("BRONZE_PATH", "./data/bronze")),
            silver_path=Path(_optional("SILVER_PATH", "./data/silver")),
            log_path=Path(_optional("LOG_PATH", "./logs/pipeline.log")),
            eor_country_codes=country_codes,
            eor_header_row=int(_optional("EOR_HEADER_ROW", "7")),
            db_host=_require("DB_HOST"),
            db_port=int(_optional("DB_PORT", "5432")),
            db_name=_require("DB_NAME"),
            db_user=_require("DB_USER"),
            db_password=_require("DB_PASSWORD"),
        )