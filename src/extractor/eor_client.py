"""Cliente para el connector elFinder (plugin WP File Manager) del EOR.

Resumen de la ingeniería inversa realizada sobre el portal
(enteoperador.org, sección "Informes Públicos de Procesos Comerciales" >
Predespacho):

  * El explorador de archivos es el plugin de WordPress "WP File Manager",
    que expone el protocolo elFinder 2.0 a través de un front controller:
        GET /?red_fm_connect=true&front=user&fid=<id>&cmd=<comando>...
  * El "hash" que usa elFinder para referenciar un archivo es determinístico:
        hash = "<volume_id>_" + base64_estandar(nombre_archivo) (sin padding)
    Esto permite calcular la URL de descarga de un archivo conocido sin
    necesidad de listar la carpeta primero.
  * El nombre de archivo sigue el patrón "PUB004-PRE-YYYYMMDD.zip".
  * La descarga se hace con: cmd=file&target=<hash>&download=1&fid=<id>
  * No requiere autenticación: la sección es de acceso público (validado
    manualmente y confirmado por descargas exitosas sin sesión).

Estos supuestos están documentados en el README del proyecto y deben
revalidarse si el portal cambia de plugin o de estructura.
"""
from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

from src.extractor.exceptions import EORFileNotFoundError, EORNetworkError
from src.extractor.fid_resolver import FidResolver


class EORClient:
    """Encapsula toda la interacción HTTP con el portal EOR."""

    def __init__(
        self,
        base_url: str,
        volume_id: str,
        report_prefix: str,
        fid_resolver: FidResolver,
        timeout: int = 30,
        session: requests.Session | None = None,
        logger=None,
    ) -> None:
        self._base_url = base_url
        self._volume_id = volume_id
        self._report_prefix = report_prefix
        self._fid_resolver = fid_resolver
        self._timeout = timeout
        self._session = session or requests.Session()
        self._logger = logger

    # -- Construcción de nombres, hashes y URLs -----------------------------

    def build_filename(self, target_date: date) -> str:
        """Nombre esperado del ZIP principal para una fecha, ej. PUB004-PRE-20260904.zip."""
        return f"{self._report_prefix}-{target_date:%Y%m%d}.zip"

    def compute_hash(self, filename: str) -> str:
        """Calcula el hash determinístico de elFinder para un nombre de archivo."""
        encoded = base64.b64encode(filename.encode("utf-8")).decode("ascii")
        encoded_no_padding = encoded.rstrip("=")
        return f"{self._volume_id}_{encoded_no_padding}"

    def build_download_url(self, target_date: date) -> str:
        """Construye la URL completa de descarga para el ZIP de `target_date`."""
        filename = self.build_filename(target_date)
        file_hash = self.compute_hash(filename)
        fid = self._fid_resolver.resolve(target_date)

        params = {
            "red_fm_connect": "true",
            "front": "user",
            "fid": fid,
            "cmd": "file",
            "target": file_hash,
            "download": "1",
        }
        return f"{self._base_url}?{urlencode(params)}"

    # -- Descarga -------------------------------------------------------------

    def download(self, target_date: date, dest_dir: Path) -> Path:
        """Descarga el ZIP de Predespacho para `target_date` a `dest_dir`.

        Returns:
            Ruta local del archivo ZIP descargado.

        Raises:
            EORFileNotFoundError: si el portal no tiene publicado el reporte
                para esa fecha (aún no publicado, día sin mercado, etc.).
            EORNetworkError: ante timeouts, errores de conexión o códigos
                HTTP de error del servidor.
        """
        url = self.build_download_url(target_date)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / self.build_filename(target_date)

        if self._logger:
            self._logger.info(
                "Descargando Predespacho fecha=%s -> %s", target_date, dest_path
            )

        try:
            response = self._session.get(url, timeout=self._timeout, stream=True)
        except requests.RequestException as exc:
            raise EORNetworkError(
                f"Fallo de red al descargar fecha={target_date}: {exc}"
            ) from exc

        if response.status_code == 404:
            raise EORFileNotFoundError(
                f"El EOR no tiene publicado el Predespacho de {target_date} "
                f"(HTTP 404)."
            )

        if not response.ok:
            raise EORNetworkError(
                f"El EOR respondió HTTP {response.status_code} para "
                f"fecha={target_date}. URL: {url}"
            )

        content_type = response.headers.get("Content-Type", "")
        if "zip" not in content_type and "octet-stream" not in content_type:
            raise EORFileNotFoundError(
                f"Respuesta inesperada (Content-Type='{content_type}') para "
                f"fecha={target_date}; probablemente el reporte no existe "
                f"para esa fecha."
            )

        with open(dest_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                fh.write(chunk)

        if self._logger:
            self._logger.info(
                "Descarga OK fecha=%s tamaño=%d bytes", target_date, dest_path.stat().st_size
            )

        return dest_path