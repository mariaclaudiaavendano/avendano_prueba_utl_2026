-- Tarea 3.1: Arrastre electoral Alianza Verde CA -> SE
-- Ratio votos_SE_Verde / votos_CA_Verde POR PUESTO (mesa) Y MUNICIPIO.
-- Homologacion: codpar_CA=5 -> codpar_SE=57
--
-- NOTA: se agrupa por (municipio, id_mesa), no solo por municipio, porque el
-- enunciado pide el ratio "por puesto y municipio". Ademas se usa un
-- UNION ALL de dos LEFT JOIN (SQLite no tiene FULL OUTER JOIN) para no perder
-- mesas que solo reportaron uno de los dos corporaciones (cobertura
-- incompleta: ver sample_data, Duitama mesa 6 no tiene datos de Senado).
WITH VotosCA AS (
    SELECT v.municipio, v.id_mesa, SUM(v.votos) AS votos_ca
    FROM votacion v
    JOIN candidatos c ON v.id_candidato = c.id_candidato
    WHERE c.corporacion = 'CA' AND c.id_partido = 5
    GROUP BY v.municipio, v.id_mesa
),
VotosSE AS (
    SELECT v.municipio, v.id_mesa, SUM(v.votos) AS votos_se
    FROM votacion v
    JOIN candidatos c ON v.id_candidato = c.id_candidato
    WHERE c.corporacion = 'SE' AND c.id_partido = 57
    GROUP BY v.municipio, v.id_mesa
)
-- Se envuelve el UNION ALL en una subquery: SQLite no resuelve de forma
-- fiable un ORDER BY por nombre de columna sobre un compound SELECT cuando
-- las ramas provienen de CTEs con columnas homonimas (se probo y falla con
-- "1st ORDER BY term does not match any column in the result set"); al
-- ordenar la subquery ya materializada se evita el problema.
SELECT * FROM (
    SELECT
        ca.municipio,
        ca.id_mesa,
        ca.votos_ca,
        se.votos_se,
        CAST(se.votos_se AS REAL) / NULLIF(ca.votos_ca, 0) AS ratio_arrastre
    FROM VotosCA ca
    LEFT JOIN VotosSE se ON ca.municipio = se.municipio AND ca.id_mesa = se.id_mesa

    UNION ALL

    SELECT
        se.municipio,
        se.id_mesa,
        ca.votos_ca,
        se.votos_se,
        CAST(se.votos_se AS REAL) / NULLIF(ca.votos_ca, 0) AS ratio_arrastre
    FROM VotosSE se
    LEFT JOIN VotosCA ca ON ca.municipio = se.municipio AND ca.id_mesa = se.id_mesa
    WHERE ca.id_mesa IS NULL  -- solo las mesas que VotosCA no cubrio, para no duplicar
)
ORDER BY municipio, id_mesa;
