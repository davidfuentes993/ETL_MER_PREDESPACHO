-- Esquema Gold: 3 tablas de hechos (una por tipo de reporte, dado que
-- tienen grano y columnas de negocio distintas), compartiendo dimensiones
-- de fecha y país.

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.dim_fecha (
    date_id     INTEGER PRIMARY KEY,       -- formato YYYYMMDD
    fecha       DATE NOT NULL UNIQUE,
    anio        SMALLINT NOT NULL,
    mes         SMALLINT NOT NULL,
    dia         SMALLINT NOT NULL,
    dia_semana  SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.dim_pais (
    country_id   SERIAL PRIMARY KEY,
    codigo_oso   VARCHAR(10) NOT NULL UNIQUE,
    nombre_pais  VARCHAR(50) NOT NULL
);

-- PEXANTE: grano = hora + nodo
CREATE TABLE IF NOT EXISTS gold.fact_pexante (
    fact_id       BIGSERIAL PRIMARY KEY,
    date_id       INTEGER NOT NULL REFERENCES gold.dim_fecha(date_id),
    country_id    INTEGER NOT NULL REFERENCES gold.dim_pais(country_id),
    hora          SMALLINT NOT NULL,
    nodo          INTEGER NOT NULL,
    precio_exante NUMERIC(10, 4),
    source_file   VARCHAR(255) NOT NULL,
    load_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date_id, country_id, hora, nodo)
);

-- TOP: grano = hora + nodo + agente + punto_medida
CREATE TABLE IF NOT EXISTS gold.fact_top (
    fact_id                    BIGSERIAL PRIMARY KEY,
    date_id                    INTEGER NOT NULL REFERENCES gold.dim_fecha(date_id),
    country_id                 INTEGER NOT NULL REFERENCES gold.dim_pais(country_id),
    hora                       SMALLINT NOT NULL,
    nodo                       INTEGER NOT NULL,
    agente                     VARCHAR(30) NOT NULL,
    punto_medida               VARCHAR(30) NOT NULL,
    tipo_transaccion           VARCHAR(5),
    mw_energia_requerida       NUMERIC(12, 4),
    mw_energia_declarada       NUMERIC(12, 4),
    precio_ofertado_bloque_1   NUMERIC(10, 4),
    mw_ofertados_bloque_1      NUMERIC(12, 4),
    precio_ofertado_bloque_2   NUMERIC(10, 4),
    mw_ofertados_bloque_2      NUMERIC(12, 4),
    precio_ofertado_bloque_3   NUMERIC(10, 4),
    mw_ofertados_bloque_3      NUMERIC(12, 4),
    precio_ofertado_bloque_4   NUMERIC(10, 4),
    mw_ofertados_bloque_4      NUMERIC(12, 4),
    precio_ofertado_bloque_5   NUMERIC(10, 4),
    mw_ofertados_bloque_5      NUMERIC(12, 4),
    precio_exante              NUMERIC(10, 4),
    mw_predespachados          NUMERIC(12, 4),
    source_file                VARCHAR(255) NOT NULL,
    load_ts                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date_id, country_id, hora, nodo, agente, punto_medida)
);

-- TCP: grano = hora + nodo + agente + codigo_contrato_firme + tipo_transaccion + punto_medida
CREATE TABLE IF NOT EXISTS gold.fact_tcp (
    fact_id                    BIGSERIAL PRIMARY KEY,
    date_id                    INTEGER NOT NULL REFERENCES gold.dim_fecha(date_id),
    country_id                 INTEGER NOT NULL REFERENCES gold.dim_pais(country_id),
    hora                       SMALLINT NOT NULL,
    nodo                       INTEGER NOT NULL,
    agente                     VARCHAR(30) NOT NULL,
    punto_medida               VARCHAR(30) NOT NULL,
    codigo_contrato_firme      VARCHAR(50) NOT NULL,
    reduccion_s_n_na           VARCHAR(5),
    agente_contraparte         VARCHAR(30),
    punto_medida_contraparte   VARCHAR(30),
    tipo_transaccion           VARCHAR(5) NOT NULL,
    tipo_contrato              VARCHAR(10),
    tipo_oferta                VARCHAR(50),
    responsable_transmision    VARCHAR(5),
    mw_energia_requerida       NUMERIC(12, 4),
    mw_energia_declarada       NUMERIC(12, 4),
    precio_ofertado_bloque_1   NUMERIC(10, 4),
    mw_ofertados_bloque_1      NUMERIC(12, 4),
    precio_ofertado_bloque_2   NUMERIC(10, 4),
    mw_ofertados_bloque_2      NUMERIC(12, 4),
    precio_ofertado_bloque_3   NUMERIC(10, 4),
    mw_ofertados_bloque_3      NUMERIC(12, 4),
    precio_ofertado_bloque_4   NUMERIC(10, 4),
    mw_ofertados_bloque_4      NUMERIC(12, 4),
    precio_ofertado_bloque_5   NUMERIC(10, 4),
    mw_ofertados_bloque_5      NUMERIC(12, 4),
    precio_exante              NUMERIC(10, 4),
    mw_predespachados          NUMERIC(12, 4),
    source_file                VARCHAR(255) NOT NULL,
    load_ts                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date_id, country_id, hora, nodo, agente, codigo_contrato_firme, tipo_transaccion, punto_medida)
);

CREATE INDEX IF NOT EXISTS idx_fact_pexante_fecha ON gold.fact_pexante (date_id);
CREATE INDEX IF NOT EXISTS idx_fact_top_fecha ON gold.fact_top (date_id);
CREATE INDEX IF NOT EXISTS idx_fact_tcp_fecha ON gold.fact_tcp (date_id);

CREATE TABLE IF NOT EXISTS gold.control_carga (
    fecha_reporte   DATE PRIMARY KEY,
    estado          VARCHAR(20) NOT NULL,
    paises_cargados INTEGER NOT NULL DEFAULT 0,
    detalle_error   TEXT,
    ultima_corrida  TIMESTAMPTZ NOT NULL DEFAULT now()
);