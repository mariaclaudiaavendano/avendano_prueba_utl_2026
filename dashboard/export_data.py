import sqlite3
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'puestos_2026.db')
DATA_JSON_PATH = os.path.join(BASE_DIR, 'dashboard', 'data.json')
INDEX_HTML_PATH = os.path.join(BASE_DIR, 'dashboard', 'index.html')

# Colores de partido obligatorios (ver PDF de la prueba). Se mapean por
# id_partido y no se toman de `partidos.color_hex` porque ese campo viene tal
# cual del JSON de origen y no esta garantizado que coincida con el hex exacto
# exigido por la prueba.
PARTY_COLORS_BY_ID = {
    5: '#007C34', 57: '#007C34',    # Alianza Verde (CA / SE)
    87: '#7B2D8B', 92: '#7B2D8B',   # Pacto Historico (CA / SE)
    10: '#1E477D',                  # Centro Democratico
    2: '#E07B00',                   # Conservador
}
DEFAULT_COLOR = '#888888'


def export_dashboard_data(db_path, output_path):
    conn = sqlite3.connect(db_path)

    # --- Comparativo: votos CA TOTALES de los 4 municipios ---
    df_comp = _read(conn, """
        SELECT v.municipio, SUM(v.votos) as total_votos
        FROM votacion v
        JOIN candidatos c ON v.id_candidato = c.id_candidato
        WHERE c.corporacion = 'CA'
        GROUP BY v.municipio
        ORDER BY v.municipio
    """)

    # --- Por municipio: top 10 candidatos CA (con partido e id_partido) ---
    df_top = _read(conn, """
        SELECT v.municipio, c.nombre_normalizado as candidato, c.id_partido,
               p.nombre as partido, SUM(v.votos) as votos
        FROM votacion v
        JOIN candidatos c ON v.id_candidato = c.id_candidato
        JOIN partidos p ON c.id_partido = p.id_partido
        WHERE c.corporacion = 'CA'
        GROUP BY v.municipio, c.nombre_normalizado, c.id_partido, p.nombre
        ORDER BY v.municipio, votos DESC
    """)

    # --- Por municipio: partido lider SE (el de mas votos de Senado) ---
    df_se = _read(conn, """
        SELECT v.municipio, p.nombre as partido, c.id_partido, SUM(v.votos) as votos
        FROM votacion v
        JOIN candidatos c ON v.id_candidato = c.id_candidato
        JOIN partidos p ON c.id_partido = p.id_partido
        WHERE c.corporacion = 'SE'
        GROUP BY v.municipio, p.nombre, c.id_partido
        ORDER BY v.municipio, votos DESC
    """)

    # --- Arrastre: ratio SE_Verde / CA_Verde por puesto (mesa) y municipio ---
    df_arrastre = _read(conn, """
        WITH VotosCA AS (
            SELECT v.municipio, v.id_mesa, SUM(v.votos) AS votos_ca
            FROM votacion v JOIN candidatos c ON v.id_candidato = c.id_candidato
            WHERE c.corporacion = 'CA' AND c.id_partido = 5
            GROUP BY v.municipio, v.id_mesa
        ),
        VotosSE AS (
            SELECT v.municipio, v.id_mesa, SUM(v.votos) AS votos_se
            FROM votacion v JOIN candidatos c ON v.id_candidato = c.id_candidato
            WHERE c.corporacion = 'SE' AND c.id_partido = 57
            GROUP BY v.municipio, v.id_mesa
        )
        SELECT ca.municipio, ca.id_mesa, ca.votos_ca, se.votos_se,
               CAST(se.votos_se AS REAL) / NULLIF(ca.votos_ca, 0) AS ratio
        FROM VotosCA ca
        LEFT JOIN VotosSE se ON ca.municipio = se.municipio AND ca.id_mesa = se.id_mesa
        ORDER BY ca.municipio, ca.id_mesa
    """)

    conn.close()

    comparativo = [
        {"municipio": row["municipio"], "total_votos_ca": row["total_votos"]}
        for row in df_comp
    ]

    municipios = {}
    for municipio in sorted({row["municipio"] for row in df_top}):
        top10 = [
            {
                "candidato": row["candidato"],
                "partido": row["partido"],
                "id_partido": row["id_partido"],
                "color": PARTY_COLORS_BY_ID.get(row["id_partido"], DEFAULT_COLOR),
                "votos": row["votos"],
            }
            for row in df_top if row["municipio"] == municipio
        ][:10]

        lideres_se = [row for row in df_se if row["municipio"] == municipio]
        lider_se = None
        if lideres_se:
            top_lider = lideres_se[0]
            lider_se = {
                "partido": top_lider["partido"],
                "id_partido": top_lider["id_partido"],
                "color": PARTY_COLORS_BY_ID.get(top_lider["id_partido"], DEFAULT_COLOR),
                "votos": top_lider["votos"],
            }

        municipios[municipio] = {"top_candidatos_ca": top10, "lider_se": lider_se}

    arrastre = {}
    for municipio in sorted({row["municipio"] for row in df_arrastre}):
        arrastre[municipio] = [
            {
                "id_mesa": row["id_mesa"],
                "votos_ca": row["votos_ca"],
                "votos_se": row["votos_se"],
                "ratio": row["ratio"],
            }
            for row in df_arrastre if row["municipio"] == municipio
        ]

    dashboard_data = {
        "colores_partido": {
            5: '#007C34', 57: '#007C34', 87: '#7B2D8B', 92: '#7B2D8B',
            10: '#1E477D', 2: '#E07B00',
        },
        "comparativo": comparativo,
        "municipios": municipios,
        "arrastre": arrastre,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
    print(f"Datos exportados a {output_path}")

    _embed_in_html(dashboard_data)


def _read(conn, query):
    conn.row_factory = sqlite3.Row
    return conn.execute(query).fetchall()


def _embed_in_html(dashboard_data):
    """Inserta los datos directamente en index.html (dentro de un <script>)
    para que el dashboard funcione abriendo el archivo con doble clic
    (file://), sin depender de fetch() ni de un servidor local: Chrome
    bloquea fetch() sobre file:// por CORS. index.html intenta fetch('data.json')
    primero (por si se sirve via http) y usa este bloque embebido como
    fallback inmediato."""
    if not os.path.exists(INDEX_HTML_PATH):
        return

    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    payload = json.dumps(dashboard_data, ensure_ascii=False)
    block = (
        '<script id="embedded-data" type="application/json">'
        f'{payload}'
        '</script>'
    )

    pattern = re.compile(
        r'<script id="embedded-data" type="application/json">.*?</script>',
        re.DOTALL,
    )
    if pattern.search(html):
        html = pattern.sub(block, html)
    else:
        html = html.replace('</head>', f'{block}\n</head>')

    with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Datos embebidos en {INDEX_HTML_PATH} (fallback sin servidor)")


if __name__ == "__main__":
    export_dashboard_data(DB_PATH, DATA_JSON_PATH)
