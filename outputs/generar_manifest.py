"""
Validador estricto de la prueba tecnica UTL Senado 2026.

Edite la seccion META antes de ejecutar. Luego corra:
    python outputs/generar_manifest.py

Imprime "4/4 municipios" y "SQL OK" para cada una de las 3 tareas SQL cuando
todo esta correcto, y escribe outputs/evaluation_manifest.json con el detalle
completo que usa el evaluador automatico.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

# ============================== META =======================================
# Edite estos 3 valores con sus datos antes de entregar.
META = {
    "nombre": "APELLIDO NOMBRE",
    "email": "correo@ejemplo.com",
    "url_repo": "https://github.com/USUARIO/apellido_prueba_utl_2026",
}
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'puestos_2026.db')
SQL_DIR = os.path.join(BASE_DIR, 'sql')
OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
VIZ_DIR = os.path.join(BASE_DIR, 'viz')

MUNICIPIOS_ESPERADOS = ["TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"]
SQL_TAREAS = ["tarea_3_1.sql", "tarea_3_2.sql", "tarea_3_3.sql"]
SCATTER_RE = re.compile(r"r=(-?\d+\.\d+)\s*\|\s*pendiente=(-?\d+\.\d+)\s*\|\s*n_mesas=(\d+)")


def check_municipios(conn):
    cur = conn.execute("SELECT DISTINCT municipio FROM votacion")
    presentes = {row[0] for row in cur.fetchall()}
    faltantes = [m for m in MUNICIPIOS_ESPERADOS if m not in presentes]
    ok_count = len(MUNICIPIOS_ESPERADOS) - len(faltantes)
    print(f"{ok_count}/4 municipios")
    return {
        "esperados": MUNICIPIOS_ESPERADOS,
        "presentes": sorted(presentes),
        "faltantes": faltantes,
        "resultado": f"{ok_count}/4 municipios",
    }


def check_conteos_por_municipio(conn):
    conteos = {}
    for municipio in MUNICIPIOS_ESPERADOS:
        filas = conn.execute(
            "SELECT COUNT(*) FROM votacion WHERE municipio = ?", (municipio,)
        ).fetchone()[0]
        mesas = conn.execute(
            "SELECT COUNT(DISTINCT id_mesa) FROM votacion WHERE municipio = ?", (municipio,)
        ).fetchone()[0]
        conteos[municipio] = {"filas_votacion": filas, "mesas": mesas}
    return conteos


def check_filas_por_tabla(conn):
    tablas = ["partidos", "candidatos", "votacion", "carga_log"]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}


def check_partido_lider_se(conn):
    lideres = {}
    for municipio in MUNICIPIOS_ESPERADOS:
        row = conn.execute("""
            SELECT p.nombre, SUM(v.votos) as total
            FROM votacion v
            JOIN candidatos c ON v.id_candidato = c.id_candidato
            JOIN partidos p ON c.id_partido = p.id_partido
            WHERE v.municipio = ? AND c.corporacion = 'SE'
            GROUP BY p.nombre
            ORDER BY total DESC
            LIMIT 1
        """, (municipio,)).fetchone()
        lideres[municipio] = {"partido": row[0], "votos": row[1]} if row else None
    return lideres


def check_idempotencia(conn):
    filas = conn.execute("SELECT filas_insertadas, filas_omitidas FROM carga_log ORDER BY id_carga").fetchall()
    if len(filas) < 2:
        return {"corridas_registradas": len(filas), "es_idempotente": None,
                "detalle": "Se necesitan al menos 2 corridas de etl.py en carga_log para verificar"}
    ultima_insertadas = filas[-1][0]
    return {
        "corridas_registradas": len(filas),
        "es_idempotente": ultima_insertadas == 0,
        "detalle": f"Ultima corrida inserto {ultima_insertadas} filas nuevas (se espera 0 en una re-ejecucion)",
    }


def run_sql_tarea(conn, filename):
    path = os.path.join(SQL_DIR, filename)
    if not os.path.exists(path):
        return {"archivo": filename, "estado": "ERROR", "detalle": "archivo no encontrado"}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            sql = f.read()
        cur = conn.execute(sql)
        columnas = [d[0] for d in cur.description] if cur.description else []
        filas = cur.fetchall()
        print(f"{filename}: SQL OK ({len(filas)} filas)")
        return {
            "archivo": filename,
            "estado": "OK",
            "columnas": columnas,
            "n_filas": len(filas),
            "muestra": [list(r) for r in filas[:5]],
        }
    except sqlite3.Error as e:
        print(f"{filename}: ERROR -> {e}")
        return {"archivo": filename, "estado": "ERROR", "detalle": str(e)}


def run_scatter_script():
    script_path = os.path.join(VIZ_DIR, 'scatter.py')
    if not os.path.exists(script_path):
        return {"estado": "ERROR", "detalle": "viz/scatter.py no encontrado"}
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=60, cwd=BASE_DIR,
        )
    except Exception as e:
        return {"estado": "ERROR", "detalle": str(e)}

    match = SCATTER_RE.search(result.stdout)
    png_path = os.path.join(VIZ_DIR, 'scatter_ca_se.png')
    png_ok = os.path.exists(png_path) and os.path.getsize(png_path) > 10 * 1024

    if not match:
        return {"estado": "ERROR", "detalle": "No se encontro la salida r=... | pendiente=... | n_mesas=... ",
                "stdout": result.stdout, "stderr": result.stderr}

    return {
        "estado": "OK",
        "r": float(match.group(1)),
        "pendiente": float(match.group(2)),
        "n_mesas": int(match.group(3)),
        "png_generado": png_ok,
        "png_bytes": os.path.getsize(png_path) if os.path.exists(png_path) else 0,
    }


def check_heatmap_png():
    png_path = os.path.join(VIZ_DIR, 'heatmap_municipios.png')
    existe = os.path.exists(png_path)
    tamano = os.path.getsize(png_path) if existe else 0
    return {"existe": existe, "bytes": tamano, "ok": existe and tamano > 10 * 1024}


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: no existe la base de datos en {DB_PATH}. Ejecute scraper.py y etl.py primero.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    municipios_result = check_municipios(conn)
    conteos = check_conteos_por_municipio(conn)
    filas_por_tabla = check_filas_por_tabla(conn)
    lideres_se = check_partido_lider_se(conn)
    idempotencia = check_idempotencia(conn)

    sql_resultados = [run_sql_tarea(conn, f) for f in SQL_TAREAS]
    conn.close()

    scatter_resultado = run_scatter_script()
    heatmap_resultado = check_heatmap_png()

    manifest = {
        "meta": META,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "reto_1_extraccion": {
            "municipios": municipios_result,
            "conteos_por_municipio": conteos,
        },
        "reto_2_base_de_datos": {
            "filas_por_tabla": filas_por_tabla,
            "partido_lider_se_por_municipio": lideres_se,
            "idempotencia_etl": idempotencia,
        },
        "reto_3_sql_analitico": sql_resultados,
        "reto_5_visualizaciones": {
            "scatter_ca_se": scatter_resultado,
            "heatmap_municipios": heatmap_resultado,
        },
    }

    output_path = os.path.join(OUTPUTS_DIR, 'evaluation_manifest.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest escrito en {output_path}")

    hubo_error_sql = any(r["estado"] == "ERROR" for r in sql_resultados)
    if hubo_error_sql:
        print("\nATENCION: al menos un archivo SQL genero ERROR. Corrijalo antes de entregar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
