"""Excepciones específicas para errores de extracción desde el portal EOR."""


class EORExtractionError(Exception):
    """Error base para cualquier falla al interactuar con el portal EOR."""


class EORFileNotFoundError(EORExtractionError):
    """El portal respondió correctamente pero el archivo del día no existe.

    Esto es distinto de un error de red: significa que, a la fecha
    solicitada, el EOR aún no ha publicado (o nunca publicó) el reporte de
    Predespacho.
    """


class EORNetworkError(EORExtractionError):
    """Falla de red, timeout, o respuesta HTTP no exitosa del portal."""