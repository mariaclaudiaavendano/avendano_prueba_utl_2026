import sqlite3
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'puestos_2026.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'db', 'schema.sql')


def normalize_name(name):
    if not name:
        return "DESCONOCIDO"
    # Normalizacion exigida: mayusculas y sin tildes
    normalized = str(name).strip().upper()
    for original, replacement in [("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ü", "U")]:
        normalized = normalized.replace(original, replacement)
    return normalized


def _extract_registros(data):
    """Soporta tanto {"resultados": [...]} como una lista JSON directa."""
    if isinstance(data, dict):
        registros = data.get('resultados', [])
    elif isinstance(data, list):
        registros = data
    else:
        registros = []
    return [r for r in registros if isinstance(r, dict)]


def run_etl(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Ejecutar Schema
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())

    # 2. Leer datos crudos del scraper
    cursor.execute("SELECT municipio, data_json FROM raw_registraduria")
    raw_records = cursor.fetchall()

    filas_insertadas = 0
    filas_omitidas = 0

    for municipio, data_json in raw_records:
        data = json.loads(data_json)
        registros = _extract_registros(data)

        for item in registros:
            try:
                id_partido = int(item.get('id_partido') or 0)
                nombre_partido = normalize_name(item.get('partido', 'VOTO BLANCO'))
                color_hex = item.get('color', '#000000')

                id_candidato = int(item.get('id_candidato') or 0)
                nombre_candidato = normalize_name(item.get('candidato', ''))
                corporacion = str(item.get('corporacion', 'CA')).upper()

                id_mesa = int(item.get('id_mesa') or 0)
                votos = int(item.get('votos') or 0)

                # Cargar Partido (Idempotente)
                cursor.execute(
                    "INSERT OR IGNORE INTO partidos (id_partido, nombre, color_hex) VALUES (?, ?, ?)",
                    (id_partido, nombre_partido, color_hex)
                )

                # Cargar Candidato (Idempotente)
                cursor.execute(
                    "INSERT OR IGNORE INTO candidatos (id_candidato, id_partido, nombre_normalizado, corporacion) VALUES (?, ?, ?, ?)",
                    (id_candidato, id_partido, nombre_candidato, corporacion)
                )

                # Cargar Votacion (Idempotente). PK = (municipio, id_mesa, id_candidato)
                cursor.execute(
                    "INSERT OR IGNORE INTO votacion (id_mesa, id_candidato, municipio, votos) VALUES (?, ?, ?, ?)",
                    (id_mesa, id_candidato, municipio, votos)
                )

                if cursor.rowcount > 0:
                    filas_insertadas += 1
                else:
                    filas_omitidas += 1

            except Exception as e:
                filas_omitidas += 1
                logging.debug(f"Registro omitido por error: {e}")

    # Log de carga obligatorio
    cursor.execute(
        "INSERT INTO carga_log (filas_insertadas, filas_omitidas) VALUES (?, ?)",
        (filas_insertadas, filas_omitidas)
    )

    conn.commit()
    conn.close()
    logging.info(f"ETL Finalizado. Insertadas: {filas_insertadas} | Omitidas: {filas_omitidas}")


if __name__ == "__main__":
    run_etl(DB_PATH)
