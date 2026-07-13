CREATE TABLE IF NOT EXISTS partidos (
    id_partido INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    color_hex TEXT
);

CREATE TABLE IF NOT EXISTS candidatos (
    id_candidato INTEGER PRIMARY KEY,
    id_partido INTEGER,
    nombre_normalizado TEXT NOT NULL,
    corporacion TEXT CHECK(corporacion IN ('CA', 'SE')) NOT NULL,
    FOREIGN KEY(id_partido) REFERENCES partidos(id_partido)
);

-- PK incluye `municipio`: el codigo de mesa (id_mesa) no es unico a nivel
-- nacional/departamental, se reutiliza en cada municipio (mesa 1, mesa 2, ...).
-- Sin `municipio` en la clave, el INSERT OR IGNORE del ETL descartaria
-- silenciosamente los votos de un municipio cuando otro ya registro el mismo
-- id_mesa + id_candidato (ej. un candidato de Camara con listado departamental
-- aparece con id_mesa=1 tanto en Tunja como en Paipa).
CREATE TABLE IF NOT EXISTS votacion (
    id_mesa INTEGER,
    id_candidato INTEGER,
    municipio TEXT NOT NULL,
    votos INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (municipio, id_mesa, id_candidato),
    FOREIGN KEY(id_candidato) REFERENCES candidatos(id_candidato)
) WITHOUT ROWID;

-- Tabla exigida en los requisitos para tracking de auditoria
CREATE TABLE IF NOT EXISTS carga_log (
    id_carga INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    filas_insertadas INTEGER,
    filas_omitidas INTEGER
);

-- Indices (bonus 2.1): cada uno respalda un patron de consulta real usado en
-- sql/tarea_3_*.sql, dashboard/export_data.py y viz/*.py.

-- 1) Todas las consultas analiticas filtran/agrupan por municipio primero
--    (comparativo del dashboard, heatmap, scatter). Acelera el filtrado y el
--    GROUP BY v.municipio sin tener que escanear toda la tabla `votacion`.
CREATE INDEX IF NOT EXISTS idx_votacion_municipio ON votacion(municipio);

-- 2) tarea_3_1/3_2/3_3 y export_data.py hacen JOIN votacion.id_candidato =
--    candidatos.id_candidato para conocer partido/corporacion de cada voto.
--    Sin este indice cada JOIN es un table scan de `votacion`.
CREATE INDEX IF NOT EXISTS idx_votacion_candidato ON votacion(id_candidato);

-- 3) tarea_3_2 (dominancia) y tarea_3_3 (atribucion) agrupan por id_mesa para
--    calcular el total de votos de un partido en una mesa especifica.
CREATE INDEX IF NOT EXISTS idx_votacion_mesa ON votacion(id_mesa);

-- 4) candidatos.corporacion se filtra en practicamente todas las queries
--    ('CA' vs 'SE'); candidatos.id_partido se usa para el JOIN con partidos
--    y para agrupar atribucion/dominancia por partido.
CREATE INDEX IF NOT EXISTS idx_candidatos_corporacion ON candidatos(corporacion);
CREATE INDEX IF NOT EXISTS idx_candidatos_partido ON candidatos(id_partido);
