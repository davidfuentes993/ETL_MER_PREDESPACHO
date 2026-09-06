"""Acceso a PostgreSQL para la capa Gold.

Toda la interacción SQL del proyecto vive en esta clase: ningún otro
módulo abre conexiones ni escribe SQL directamente.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SCHEMA_SQL_PATH = Path(__file__).resolve().parent.parent.parent / "sql" / "schema.sql"


class PostgresRepository:
    """Encapsula todas las operaciones de base de datos de la capa Gold."""

    def __init__(self, dsn: str, logger=None) -> None:
        self._engine: Engine = create_engine(dsn, pool_pre_ping=True)
        self._logger = logger

    def ensure_schema(self) -> None:
        """Crea el esquema/tablas si no existen, a partir de sql/schema.sql."""
        ddl = SCHEMA_SQL_PATH.read_text(encoding="utf-8")

        statements = []
        for raw_statement in ddl.split(";"):
            # Elimina cada línea de comentario dentro de esta sentencia,
            # no solo verifica si la sentencia completa es un comentario.
            lines = [
                line for line in raw_statement.splitlines()
                if not line.strip().startswith("--")
            ]
            statement = "\n".join(lines).strip()
            if statement:
                statements.append(statement)

        with self._engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))

        if self._logger:
            self._logger.info("Esquema Gold verificado/creado en PostgreSQL.")


    def get_or_create_country(self, codigo_oso: str, nombre_pais: str) -> int:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO gold.dim_pais (codigo_oso, nombre_pais)
                    VALUES (:codigo_oso, :nombre_pais)
                    ON CONFLICT (codigo_oso) DO NOTHING
                    """
                ),
                {"codigo_oso": codigo_oso, "nombre_pais": nombre_pais},
            )
            row = conn.execute(
                text("SELECT country_id FROM gold.dim_pais WHERE codigo_oso = :codigo_oso"),
                {"codigo_oso": codigo_oso},
            ).one()
        return row.country_id

    def get_or_create_date(self, fecha: date) -> int:
        date_id = int(fecha.strftime("%Y%m%d"))
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO gold.dim_fecha (date_id, fecha, anio, mes, dia, dia_semana)
                    VALUES (:date_id, :fecha, :anio, :mes, :dia, :dia_semana)
                    ON CONFLICT (date_id) DO NOTHING
                    """
                ),
                {
                    "date_id": date_id,
                    "fecha": fecha,
                    "anio": fecha.year,
                    "mes": fecha.month,
                    "dia": fecha.day,
                    "dia_semana": fecha.weekday(),
                },
            )
        return date_id

    # -- Hechos: PEXANTE -------------------------------------------------------

    def insert_fact_pexante_rows(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO gold.fact_pexante
                        (date_id, country_id, hora, nodo, precio_exante, source_file)
                    VALUES
                        (:date_id, :country_id, :hora, :nodo, :precio_exante, :source_file)
                    ON CONFLICT (date_id, country_id, hora, nodo) DO NOTHING
                    """
                ),
                rows,
            )
        return result.rowcount or 0

    # -- Hechos: TOP -------------------------------------------------------------

    def insert_fact_top_rows(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO gold.fact_top
                        (date_id, country_id, hora, nodo, agente, punto_medida,
                         tipo_transaccion, mw_energia_requerida, mw_energia_declarada,
                         precio_ofertado_bloque_1, mw_ofertados_bloque_1,
                         precio_ofertado_bloque_2, mw_ofertados_bloque_2,
                         precio_ofertado_bloque_3, mw_ofertados_bloque_3,
                         precio_ofertado_bloque_4, mw_ofertados_bloque_4,
                         precio_ofertado_bloque_5, mw_ofertados_bloque_5,
                         precio_exante, mw_predespachados, source_file)
                    VALUES
                        (:date_id, :country_id, :hora, :nodo, :agente, :punto_medida,
                         :tipo_transaccion, :mw_energia_requerida, :mw_energia_declarada,
                         :precio_ofertado_bloque_1, :mw_ofertados_bloque_1,
                         :precio_ofertado_bloque_2, :mw_ofertados_bloque_2,
                         :precio_ofertado_bloque_3, :mw_ofertados_bloque_3,
                         :precio_ofertado_bloque_4, :mw_ofertados_bloque_4,
                         :precio_ofertado_bloque_5, :mw_ofertados_bloque_5,
                         :precio_exante, :mw_predespachados, :source_file)
                    ON CONFLICT (date_id, country_id, hora, nodo, agente, punto_medida) DO NOTHING
                    """
                ),
                rows,
            )
        return result.rowcount or 0

    # -- Hechos: TCP -------------------------------------------------------------

    def insert_fact_tcp_rows(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO gold.fact_tcp
                        (date_id, country_id, hora, nodo, agente, punto_medida,
                         codigo_contrato_firme, reduccion_s_n_na, agente_contraparte,
                         punto_medida_contraparte, tipo_transaccion, tipo_contrato,
                         tipo_oferta, responsable_transmision,
                         mw_energia_requerida, mw_energia_declarada,
                         precio_ofertado_bloque_1, mw_ofertados_bloque_1,
                         precio_ofertado_bloque_2, mw_ofertados_bloque_2,
                         precio_ofertado_bloque_3, mw_ofertados_bloque_3,
                         precio_ofertado_bloque_4, mw_ofertados_bloque_4,
                         precio_ofertado_bloque_5, mw_ofertados_bloque_5,
                         precio_exante, mw_predespachados, source_file)
                    VALUES
                        (:date_id, :country_id, :hora, :nodo, :agente, :punto_medida,
                         :codigo_contrato_firme, :reduccion_s_n_na, :agente_contraparte,
                         :punto_medida_contraparte, :tipo_transaccion, :tipo_contrato,
                         :tipo_oferta, :responsable_transmision,
                         :mw_energia_requerida, :mw_energia_declarada,
                         :precio_ofertado_bloque_1, :mw_ofertados_bloque_1,
                         :precio_ofertado_bloque_2, :mw_ofertados_bloque_2,
                         :precio_ofertado_bloque_3, :mw_ofertados_bloque_3,
                         :precio_ofertado_bloque_4, :mw_ofertados_bloque_4,
                         :precio_ofertado_bloque_5, :mw_ofertados_bloque_5,
                         :precio_exante, :mw_predespachados, :source_file)
                    ON CONFLICT (date_id, country_id, hora, nodo, agente, codigo_contrato_firme,
                                 tipo_transaccion, punto_medida) DO NOTHING
                    """
                ),
                rows,
            )
        return result.rowcount or 0

    # -- Control de carga --------------------------------------------------------

    def upsert_control_carga(
        self, fecha_reporte: date, estado: str, paises_cargados: int, detalle_error: str | None = None
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO gold.control_carga (fecha_reporte, estado, paises_cargados, detalle_error)
                    VALUES (:fecha_reporte, :estado, :paises_cargados, :detalle_error)
                    ON CONFLICT (fecha_reporte) DO UPDATE SET
                        estado = EXCLUDED.estado,
                        paises_cargados = EXCLUDED.paises_cargados,
                        detalle_error = EXCLUDED.detalle_error,
                        ultima_corrida = now()
                    """
                ),
                {
                    "fecha_reporte": fecha_reporte,
                    "estado": estado,
                    "paises_cargados": paises_cargados,
                    "detalle_error": detalle_error,
                },
            )

    def fecha_ya_cargada(self, fecha_reporte: date) -> bool:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT estado FROM gold.control_carga WHERE fecha_reporte = :fecha"),
                {"fecha": fecha_reporte},
            ).one_or_none()
        return row is not None and row.estado == "OK"