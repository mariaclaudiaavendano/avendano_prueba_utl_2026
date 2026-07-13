-- Tarea 3.2: Dominancia extrema
-- Mesas donde un candidato concentra >60% de los votos de su partido.
--
-- IMPORTANTE: el total del partido en la mesa se calcula por
-- (id_mesa, id_partido, corporacion), no solo (id_mesa, id_partido). Un mismo
-- partido tiene candidatos tanto en Camara como en Senado (codpar_CD=10 y
-- codpar_CON=2 se repiten en ambas corporaciones); si no se separa por
-- corporacion, se mezclarian votos de Camara y Senado del mismo partido en la
-- misma mesa, inflando artificialmente -o diluyendo- el denominador.
WITH TotalMesaPartido AS (
    SELECT v.id_mesa, v.municipio, c.id_partido, c.corporacion,
           SUM(v.votos) AS total_partido_mesa
    FROM votacion v
    JOIN candidatos c ON v.id_candidato = c.id_candidato
    GROUP BY v.id_mesa, v.municipio, c.id_partido, c.corporacion
)
SELECT
    v.municipio,
    v.id_mesa,
    c.nombre_normalizado,
    c.id_partido,
    c.corporacion,
    v.votos,
    tmp.total_partido_mesa,
    CAST(v.votos AS REAL) / tmp.total_partido_mesa AS porcentaje_dominancia
FROM votacion v
JOIN candidatos c ON v.id_candidato = c.id_candidato
JOIN TotalMesaPartido tmp
    ON v.id_mesa = tmp.id_mesa
    AND v.municipio = tmp.municipio
    AND c.id_partido = tmp.id_partido
    AND c.corporacion = tmp.corporacion
WHERE (CAST(v.votos AS REAL) / tmp.total_partido_mesa) > 0.60
ORDER BY porcentaje_dominancia DESC;
