-- Tarea 3.3: Atribucion deterministica
-- Top 5 candidatos por atribucion SE consolidada.
-- Formula: A_ij = (votos_cand / votos_partido) x votos_SE_partido
WITH VotosCandidato AS (
    SELECT v.id_candidato, c.id_partido, SUM(v.votos) AS votos_cand
    FROM votacion v JOIN candidatos c ON v.id_candidato = c.id_candidato
    WHERE c.corporacion = 'CA'
    GROUP BY v.id_candidato, c.id_partido
),
VotosPartidoCA AS (
    SELECT id_partido, SUM(votos_cand) AS votos_partido
    FROM VotosCandidato GROUP BY id_partido
),
VotosPartidoSE AS (
    SELECT c.id_partido, SUM(v.votos) AS votos_SE_partido
    FROM votacion v JOIN candidatos c ON v.id_candidato = c.id_candidato
    WHERE c.corporacion = 'SE'
    GROUP BY c.id_partido
)
SELECT
    vc.id_candidato,
    cand.nombre_normalizado,
    p.nombre AS partido,
    vc.votos_cand,
    vpse.votos_SE_partido,
    (CAST(vc.votos_cand AS REAL) / NULLIF(vpc.votos_partido, 0)) * vpse.votos_SE_partido AS atribucion
FROM VotosCandidato vc
JOIN VotosPartidoCA vpc ON vc.id_partido = vpc.id_partido
JOIN VotosPartidoSE vpse ON vc.id_partido = vpse.id_partido
JOIN candidatos cand ON cand.id_candidato = vc.id_candidato
JOIN partidos p ON p.id_partido = vc.id_partido
ORDER BY atribucion DESC
LIMIT 5;
