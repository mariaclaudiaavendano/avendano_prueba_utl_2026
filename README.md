# Avendaño — Prueba Técnica UTL Senado 2026

Pipeline de datos electorales para 4 municipios de Boyacá (Tunja, Paipa, Sogamoso, Duitama) — Congreso 2026.


## Instalación

Requiere Python 3.10+ (probado con 3.12/3.14). Recomendado usar un entorno virtual.

```bash
git clone https://github.com/TU_USUARIO/apellido_prueba_utl_2026.git
cd apellido_prueba_utl_2026
python3 -m venv venv
source venv/bin/activate       # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Pipeline de ejecución

Todos los scripts resuelven sus rutas de forma absoluta a partir de su propia
ubicación (`os.path.dirname(os.path.abspath(__file__))`), por lo que pueden
ejecutarse desde cualquier directorio de trabajo. El pipeline completo toma
menos de 1 minuto:

```bash
# 1) Extracción (API -> fallback automático a sample_data/ si la API falla)
python scraper/scraper.py                          # los 4 municipios
python scraper/scraper.py --municipios TUNJA PAIPA  # subconjunto
python scraper/scraper.py --preflight               # conteo sin descargar (bonus)

# 2) Carga a SQLite (idempotente: se puede re-ejecutar sin duplicar)
python db/etl.py

# 3) Validación de SQL + generación del manifest de evaluación
#    (edite la seccion META en outputs/generar_manifest.py con sus datos antes)
python outputs/generar_manifest.py

# 4) Exportar datos para el dashboard (data.json + embebido en index.html)
python dashboard/export_data.py

# 5) Visualizaciones
python viz/heatmap.py
python viz/scatter.py

# 6) Abrir el dashboard (doble clic o):
open dashboard/index.html      # macOS
```

Re-ejecutar `scraper/scraper.py` y `db/etl.py` no duplica filas: la tabla
`raw_registraduria` usa `municipio` como PRIMARY KEY y todas las tablas del
schema (`partidos`, `candidatos`, `votacion`) usan `INSERT OR IGNORE` sobre
claves únicas.

## API

**Dominio base:** `https://resultadospreccongreso2026.registraduria.gov.co`
(sitio real de preconteo de la Registraduría para las elecciones de Congreso
2026 — responde HTTP 200).

Endpoints confirmados durante el mapeo (F12 → Network) desde el sitio:

| Endpoint | Contenido |
|---|---|
| `GET /json/web/config.json` | Configuración de la elección: corporaciones (`SENADO`, `CAMARA`, ...), niveles geográficos (`COLOMBIA` → `DEPARTAMENTO` → `MUNICIPIO` → `ZONA` → `COMUNA` → `PUESTO` → `MESA`) y colores oficiales por ámbito. |
| `GET /json/nomenclator.json` | Nomenclator jerárquico: cada departamento trae su código (`BOYACA` = `"0700"`) y la lista de códigos numéricos de sus municipios (para Boyacá: `62, 87, 97, 137, ...`). No incluye el nombre del municipio junto al código en la misma respuesta — hay que cruzarlo con el árbol `h` de nivel 3. |
| Rutas de la SPA | `/resultados/{elec}/{ambito}/{sub}` donde `elec`: `0=SENADO`, `1=CAMARA`, `2=CONSULTAS`, `3=CITREP`. La navegación es 100% client-side (React/Vite) y el endpoint granular de resultados por mesa se dispara vía `fetch` después de la hidratación del bundle — no se pudo capturar su URL exacta navegando con herramientas automatizadas de solo-lectura en el tiempo disponible. |
| `GET /api/v1/resultados/{municipio}` (intento del scraper) | Responde `HTTP 404`. Es la ruta que se documentó como hipótesis inicial (siguiendo el patrón REST del resto de la prueba); no corresponde al endpoint real de la SPA. |

**Cabeceras HTTP:** ninguna cabecera especial fue necesaria para las
peticiones GET anteriores (sin API key, sin cookies de sesión); solo el
`User-Agent` por defecto de `requests`.

**Fallback documentado:** dado que no fue posible confirmar en el tiempo
disponible el endpoint JSON exacto que expone los resultados por mesa,
`scraper/scraper.py` intenta primero la API y, ante cualquier error HTTP
(404, timeout, 5xx con reintentos agotados), cae automáticamente a los
archivos en `sample_data/` — tal como lo permite el enunciado de la prueba.

**8 campos JSON usados** (presentes en cada registro de `sample_data/*.json`
y consumidos por `db/etl.py`):

`id_mesa`, `id_partido`, `partido`, `color`, `id_candidato`, `candidato`, `corporacion` (`CA`/`SE`), `votos`.

## Municipios en la BD

| Municipio | Filas en `votacion` | Mesas |
|---|---|---|
| TUNJA | 120 | 6 |
| PAIPA | 120 | 6 |
| SOGAMOSO | 120 | 6 |
| DUITAMA | 112 | 6 |

(Duitama tiene 8 filas menos porque la mesa 6 no reportó datos de Senado en
`sample_data/resultados_duitama.json` — cobertura incompleta usada a
propósito para probar `sql/tarea_3_1.sql`.)

## Hallazgos principales

* **Arrastre Verde CA→SE** (`sql/tarea_3_1.sql`): el ratio SE/CA varía
  fuertemente por puesto (0.46 a 2.0), lo que indica que el arrastre del
  partido no es uniforme dentro de un mismo municipio — agregar solo a nivel
  de municipio (como hacía la consulta original) ocultaba esta dispersión.
* **Correlación CA vs SE** (`viz/scatter.py`): `r=0.727 | pendiente=1.036 | n_mesas=23`.
  Una mesa (Duitama, mesa 6) quedó fuera del cálculo por no tener votos de
  Senado registrados.
* **Dominancia extrema** (`sql/tarea_3_2.sql`): 48 combinaciones mesa/partido
  superan el 60% de concentración en un solo candidato, separando
  correctamente Cámara y Senado del mismo partido en la misma mesa.
* **Atribución SE** (`sql/tarea_3_3.sql`): el top 5 por atribución
  consolidada está dominado por Conservador y Centro Democrático, no por
  Alianza Verde — ver explicación en Bonus.

## Bonus implementados

* **`--preflight` en el scraper** (+3): `python scraper/scraper.py --preflight`
  cuenta filas y mesas disponibles en `sample_data/` sin escribir en la BD.
* **3 índices SQLite con justificación** (+2, en realidad se agregaron 5 en
  `db/schema.sql`): `idx_votacion_municipio` (filtra/agrupa por municipio en
  casi todas las consultas), `idx_votacion_candidato` y `idx_votacion_mesa`
  (aceleran los JOIN y GROUP BY de `sql/tarea_3_*.sql`), `idx_candidatos_corporacion`
  e `idx_candidatos_partido` (filtran CA/SE y agrupan por partido). Cada uno
  tiene su comentario de justificación en el propio `schema.sql`.
* **Por qué el top CA no siempre es el top en atribución SE** (+2): la
  atribución SE de un candidato depende de `votos_cand / votos_partido`
  (su peso *dentro* de su propio partido en Cámara), multiplicado por el
  total de votos de Senado *de ese partido*. Un candidato puede ganar en
  votos absolutos de Cámara pero pertenecer a un partido con poco arrastre
  en Senado, mientras que un candidato con menos votos CA pero que
  concentra un porcentaje mayor de su partido, y cuyo partido tiene un SE
  fuerte, termina con mayor atribución. Es decir: popularidad individual
  (CA) vs. peso relativo dentro del partido × fuerza del partido en la otra
  corporación (SE) son cantidades distintas.
* **Dark mode toggle con CSS custom properties** (+3): botón "Modo oscuro"
  en `dashboard/index.html`, implementado con variables `--bg`, `--fg`,
  `--card-bg`, etc. sobreescritas mediante `[data-theme="dark"]`.
  Persistido en `localStorage`.
* **Botón Exportar CSV funcional** (+2): exporta el top 10 de candidatos CA
  del municipio seleccionado en el dashboard.
