-- ============================================================
-- ESQUEMA ALTERNATIVO (NO usado en el proyecto) — con dim_nodo
-- y dim_agente como dimensiones propias, para comparación.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.dim_fecha (
    date_id     INTEGER PRIMARY KEY,
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

-- Nueva dimensión: un nodo del sistema eléctrico regional.
CREATE TABLE IF NOT EXISTS gold.dim_nodo (
    nodo_id      SERIAL PRIMARY KEY,
    codigo_nodo  INTEGER NOT NULL UNIQUE
    -- Aquí irían atributos descriptivos si el EOR los publicara algún día:
    -- nombre_subestacion, departamento, nivel_tension, etc.
);

-- Nueva dimensión: un agente/participante del mercado.
CREATE TABLE IF NOT EXISTS gold.dim_agente (
    agente_id      SERIAL PRIMARY KEY,
    codigo_agente  VARCHAR(30) NOT NULL UNIQUE
    -- Igual: nombre_comercial, tipo_agente (generador/comercializador), etc.
);

CREATE TABLE IF NOT EXISTS gold.fact_pexante (
    fact_id       BIGSERIAL PRIMARY KEY,
    date_id       INTEGER NOT NULL REFERENCES gold.dim_fecha(date_id),
    country_id    INTEGER NOT NULL REFERENCES gold.dim_pais(country_id),
    nodo_id       INTEGER NOT NULL REFERENCES gold.dim_nodo(nodo_id),
    hora          SMALLINT NOT NULL,
    precio_exante NUMERIC(10, 4),
    source_file   VARCHAR(255) NOT NULL,
    load_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date_id, country_id, hora, nodo_id)
);

CREATE TABLE IF NOT EXISTS gold.fact_top (
    fact_id                  BIGSERIAL PRIMARY KEY,
    date_id                  INTEGER NOT NULL REFERENCES gold.dim_fecha(date_id),
    country_id               INTEGER NOT NULL REFERENCES gold.dim_pais(country_id),
    nodo_id                  INTEGER NOT NULL REFERENCES gold.dim_nodo(nodo_id),
    agente_id                INTEGER NOT NULL REFERENCES gold.dim_agente(agente_id),
    hora                     SMALLINT NOT NULL,
    punto_medida             VARCHAR(30) NOT NULL,
    tipo_transaccion         VARCHAR(5),
    mw_energia_requerida     NUMERIC(12, 4),
    mw_energia_declarada     NUMERIC(12, 4),
    precio_ofertado_bloque_1 NUMERIC(10, 4),
    mw_ofertados_bloque_1    NUMERIC(12, 4),
    -- ... (bloques 2-5 igual que en el esquema real) ...
    precio_exante            NUMERIC(10, 4),
    mw_predespachados        NUMERIC(12, 4),
    source_file              VARCHAR(255) NOT NULL,
    load_ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date_id, country_id, hora, nodo_id, agente_id, punto_medida)
);

-- TCP tiene un caso especial interesante: "Agente" Y "Agente Contraparte"
-- son ambos códigos de agente, pero juegan roles distintos en la misma fila.
-- Esto se llama "role-playing dimension": la MISMA tabla dim_agente se
-- referencia dos veces con dos FK distintas.
CREATE TABLE IF NOT EXISTS gold.fact_tcp (
    fact_id                  BIGSERIAL PRIMARY KEY,
    date_id                  INTEGER NOT NULL REFERENCES gold.dim_fecha(date_id),
    country_id               INTEGER NOT NULL REFERENCES gold.dim_pais(country_id),
    nodo_id                  INTEGER NOT NULL REFERENCES gold.dim_nodo(nodo_id),
    agente_id                INTEGER NOT NULL REFERENCES gold.dim_agente(agente_id),
    agente_contraparte_id    INTEGER REFERENCES gold.dim_agente(agente_id),  -- misma dim_agente, rol distinto
    hora                     SMALLINT NOT NULL,
    punto_medida             VARCHAR(30) NOT NULL,
    codigo_contrato_firme    VARCHAR(50) NOT NULL,
    tipo_transaccion         VARCHAR(5) NOT NULL,
    -- ... resto de columnas igual que en el esquema real ...
    precio_exante            NUMERIC(10, 4),
    mw_predespachados        NUMERIC(12, 4),
    source_file              VARCHAR(255) NOT NULL,
    load_ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date_id, country_id, hora, nodo_id, agente_id, codigo_contrato_firme, tipo_transaccion, punto_medida)
);