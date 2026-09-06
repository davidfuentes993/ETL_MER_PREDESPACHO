"""Resolución del 'fid' (folder id) de elFinder según la fecha solicitada.

Se determinó explorando el portal que el EOR expone dos carpetas distintas
para Predespacho:

  - "Predespacho" (fid configurable, ver EOR_FID_RECIENTE): cubre desde
    2019-01-01 hasta la fecha actual.
  - "Histórico"   (fid configurable, ver EOR_FID_HISTORICO): cubre desde
    2013-01-01 hasta 2019-04-09.

Existe un pequeño solape entre 2019-01-01 y 2019-04-09 presente en ambas
carpetas; se resuelve siempre a favor de "Predespacho" por ser la fuente
única para todo lo posterior al corte.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FidResolver:
    """Decide el fid correcto de elFinder para una fecha dada.

    Attributes:
        fid_reciente: fid de la carpeta "Predespacho" (>= cutoff_date).
        fid_historico: fid de la carpeta "Histórico" (< cutoff_date).
        cutoff_date: fecha de corte entre ambas carpetas (inclusive para
            fid_reciente).
    """

    fid_reciente: str
    fid_historico: str
    cutoff_date: date

    def resolve(self, target_date: date) -> str:
        """Devuelve el fid que corresponde consultar para `target_date`."""
        if target_date >= self.cutoff_date:
            return self.fid_reciente
        return self.fid_historico