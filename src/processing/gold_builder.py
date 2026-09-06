"""Capa Gold: lee los Parquet de Silver y los carga al modelo dimensional.

Cada tipo de reporte (TCP, TOP, PEXANTE) tiene su propia tabla de hechos
(ver sql/schema.sql), porque tienen grano y columnas de negocio distintos.
Este builder resuelve las dimensiones compartidas (fecha, país) y despacha
la inserción al método correcto de PostgresRepository según tipo_reporte.
"""
from __future__ import annotations

import pandas as pd

from src.db.postgres_repository import PostgresRepository
from src.processing.silver_transformer import SilverOutput

# Columnas de negocio que corresponden a cada tabla de hechos, en el mismo
# orden/nombre que sql/schema.sql. Las columnas de metadata (fecha_reporte,
# pais_codigo, pais_nombre, tipo_reporte) no se incluyen aquí porque se
# resuelven como date_id/country_id (FKs), no como columnas propias del hecho.
PEXANTE_COLUMNS = ["hora", "nodo", "precio_exante"]

TOP_COLUMNS = [
    "hora", "nodo", "agente", "punto_medida", "tipo_transaccion",
    "mw_energia_requerida", "mw_energia_declarada",
    "precio_ofertado_bloque_1", "mw_ofertados_bloque_1",
    "precio_ofertado_bloque_2", "mw_ofertados_bloque_2",
    "precio_ofertado_bloque_3", "mw_ofertados_bloque_3",
    "precio_ofertado_bloque_4", "mw_ofertados_bloque_4",
    "precio_ofertado_bloque_5", "mw_ofertados_bloque_5",
    "precio_exante", "mw_predespachados",
]

TCP_COLUMNS = TOP_COLUMNS + [
    "codigo_contrato_firme", "reduccion_s_n_na", "agente_contraparte",
    "punto_medida_contraparte", "tipo_contrato", "tipo_oferta",
    "responsable_transmision",
]


class GoldBuilder:
    """Construye y carga las filas de hechos a partir de un SilverOutput."""

    def __init__(self, repository: PostgresRepository, logger=None) -> None:
        self._repository = repository
        self._logger = logger

        # Despacho por tipo de reporte: cada entrada empareja las columnas
        # que hay que extraer del Parquet con el método de inserción real.
        self._dispatch = {
            "PEXANTE": (PEXANTE_COLUMNS, self._repository.insert_fact_pexante_rows),
            "TOP": (TOP_COLUMNS, self._repository.insert_fact_top_rows),
            "TCP": (TCP_COLUMNS, self._repository.insert_fact_tcp_rows),
        }

    def load_silver_output(self, silver_output: SilverOutput) -> int:
        """Carga un Parquet de Silver al esquema Gold. Devuelve filas insertadas."""
        df = pd.read_parquet(silver_output.parquet_path)

        date_id = self._repository.get_or_create_date(silver_output.fecha_reporte)
        country_id = self._repository.get_or_create_country(
            silver_output.pais_codigo,
            df["pais_nombre"].iloc[0] if len(df) else silver_output.pais_codigo,
        )

        entry = self._dispatch.get(silver_output.tipo_reporte)
        if entry is None:
            raise ValueError(f"Tipo de reporte desconocido: {silver_output.tipo_reporte}")
        columns, insert_method = entry

        rows = self._build_rows(df, columns, date_id, country_id, silver_output.parquet_path.name)
        inserted = insert_method(rows)

        if self._logger:
            self._logger.info(
                "Gold: %d filas insertadas para pais=%s tipo=%s fecha=%s",
                inserted,
                silver_output.pais_codigo,
                silver_output.tipo_reporte,
                silver_output.fecha_reporte,
            )
        return inserted

    @staticmethod
    def _build_rows(
        df: pd.DataFrame,
        columns: list[str],
        date_id: int,
        country_id: int,
        source_file: str,
    ) -> list[dict]:
        records = df[columns].to_dict(orient="records")
        rows = []
        for record in records:
            # Convierte tipos numpy (int64, float64) a tipos nativos de
            # Python, porque psycopg2 no sabe adaptar tipos numpy.
            clean_record = {
                k: (v.item() if hasattr(v, "item") else v) for k, v in record.items()
            }
            clean_record["date_id"] = date_id
            clean_record["country_id"] = country_id
            clean_record["source_file"] = source_file
            rows.append(clean_record)
        return rows