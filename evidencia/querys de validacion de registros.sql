-- ============================================================
-- Consultas de evidencia 
-- ============================================================

-- ------------------------------------------------------------
-- 1. RESUMEN GENERAL: conteo total de filas por tabla
-- ------------------------------------------------------------
SELECT 'fact_tcp' AS tabla, COUNT(*) AS filas FROM gold.fact_tcp
UNION ALL
SELECT 'fact_top', COUNT(*) FROM gold.fact_top
UNION ALL
SELECT 'fact_pexante', COUNT(*) FROM gold.fact_pexante
UNION ALL
SELECT 'dim_fecha', COUNT(*) FROM gold.dim_fecha
UNION ALL
SELECT 'dim_pais', COUNT(*) FROM gold.dim_pais
ORDER BY tabla;

-- ------------------------------------------------------------
-- 2. RANGO DE FECHAS CARGADAS (histórico disponible)
-- ------------------------------------------------------------
SELECT
    MIN(fecha) AS fecha_mas_antigua,
    MAX(fecha) AS fecha_mas_reciente,
    COUNT(DISTINCT fecha) AS dias_distintos_cargados
FROM gold.dim_fecha;

-- ------------------------------------------------------------
-- 3. ESTADO DE CARGA POR FECHA (tabla de control)
-- ------------------------------------------------------------
SELECT fecha_reporte, estado, paises_cargados, ultima_corrida
FROM gold.control_carga
ORDER BY fecha_reporte DESC;

-- Resumen de estados (cuántas fechas OK / PARCIAL / ERROR en total)
SELECT estado, COUNT(*) AS cantidad_fechas
FROM gold.control_carga
GROUP BY estado
ORDER BY estado;

-- ------------------------------------------------------------
-- 4. CANTIDAD DE REGISTROS POR FECHA (por tabla de hechos)
-- ------------------------------------------------------------
SELECT d.fecha, COUNT(*) AS filas_tcp
FROM gold.fact_tcp f
JOIN gold.dim_fecha d ON d.date_id = f.date_id
GROUP BY d.fecha
ORDER BY d.fecha;

SELECT d.fecha, COUNT(*) AS filas_top
FROM gold.fact_top f
JOIN gold.dim_fecha d ON d.date_id = f.date_id
GROUP BY d.fecha
ORDER BY d.fecha;

SELECT d.fecha, COUNT(*) AS filas_pexante
FROM gold.fact_pexante f
JOIN gold.dim_fecha d ON d.date_id = f.date_id
GROUP BY d.fecha
ORDER BY d.fecha;

-- ------------------------------------------------------------
-- 5. CANTIDAD DE REGISTROS POR PAÍS (todas las fechas)
-- ------------------------------------------------------------
SELECT p.nombre_pais, p.codigo_oso,
       COUNT(*) AS filas_top
FROM gold.fact_top f
JOIN gold.dim_pais p ON p.country_id = f.country_id
GROUP BY p.nombre_pais, p.codigo_oso
ORDER BY filas_top DESC;

-- Mismo desglose pero para las 3 tablas de hechos combinadas
SELECT
    p.nombre_pais,
    COUNT(*) FILTER (WHERE origen = 'TCP')      AS filas_tcp,
    COUNT(*) FILTER (WHERE origen = 'TOP')      AS filas_top,
    COUNT(*) FILTER (WHERE origen = 'PEXANTE')  AS filas_pexante
FROM (
    SELECT country_id, 'TCP' AS origen FROM gold.fact_tcp
    UNION ALL
    SELECT country_id, 'TOP' FROM gold.fact_top
    UNION ALL
    SELECT country_id, 'PEXANTE' FROM gold.fact_pexante
) t
JOIN gold.dim_pais p ON p.country_id = t.country_id
GROUP BY p.nombre_pais
ORDER BY p.nombre_pais;

-- ------------------------------------------------------------
-- 6. CANTIDAD DE REGISTROS POR FECHA + PAÍS (detalle cruzado)
-- ------------------------------------------------------------
SELECT d.fecha, p.nombre_pais, COUNT(*) AS filas
FROM gold.fact_top f
JOIN gold.dim_fecha d ON d.date_id = f.date_id
JOIN gold.dim_pais p ON p.country_id = f.country_id
GROUP BY d.fecha, p.nombre_pais
ORDER BY d.fecha, p.nombre_pais;
