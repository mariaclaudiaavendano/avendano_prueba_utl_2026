import argparse
import requests
import sqlite3
import json
import logging
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Rutas absolutas basadas en la ubicación de este script, para que el scraper
# funcione sin importar desde qué directorio se invoque `python scraper.py`.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'puestos_2026.db')
SAMPLE_DATA_DIR = os.path.join(BASE_DIR, 'sample_data')


def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Tabla staging para guardar la data cruda de forma idempotente
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_registraduria (
            municipio TEXT PRIMARY KEY,
            data_json TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def _find_sample_file(municipio):
    if not os.path.exists(SAMPLE_DATA_DIR):
        logging.error(f"¡El directorio no existe! Ruta buscada: {SAMPLE_DATA_DIR}")
        return None

    archivos = os.listdir(SAMPLE_DATA_DIR)
    if not archivos:
        logging.error(f"La carpeta {SAMPLE_DATA_DIR} está VACÍA. Falta descargar los datos.")
        return None

    for filename in archivos:
        if municipio.lower() in filename.lower() and filename.endswith('.json'):
            return os.path.join(SAMPLE_DATA_DIR, filename)

    logging.error(f"No hay ningún JSON que coincida con el nombre '{municipio}' en {SAMPLE_DATA_DIR}")
    return None


def fetch_data_with_fallback(session, municipio):
    url = f"https://resultadospreccongreso2026.registraduria.gov.co/api/v1/resultados/{municipio}"

    try:
        logging.info(f"Extrayendo datos para {municipio} desde API...")
        response = session.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException:
        logging.warning(f"Fallo API para {municipio}. Buscando en sample_data/...")
        filepath = _find_sample_file(municipio)
        if filepath is None:
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


def preflight_count(municipio):
    """Cuenta mesas y filas disponibles sin descargar (usa sample_data/ como fuente offline)."""
    filepath = _find_sample_file(municipio)
    if filepath is None:
        logging.info(f"[PREFLIGHT] {municipio}: sin datos locales disponibles.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    registros = data.get('resultados', data) if isinstance(data, dict) else data
    mesas = {item.get('id_mesa') for item in registros if isinstance(item, dict)}
    logging.info(f"[PREFLIGHT] {municipio}: {len(registros)} filas | {len(mesas)} mesas (fuente: {os.path.basename(filepath)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--municipios', nargs='+', default=['TUNJA', 'PAIPA', 'SOGAMOSO', 'DUITAMA'])
    parser.add_argument('--preflight', action='store_true', help='Muestra conteo de filas/mesas sin descargar ni escribir en la BD')
    args = parser.parse_args()

    if args.preflight:
        for mun in args.municipios:
            preflight_count(mun)
        raise SystemExit(0)

    conn = init_db(DB_PATH)
    cursor = conn.cursor()
    session = get_session()

    for mun in args.municipios:
        data = fetch_data_with_fallback(session, mun)
        if data:
            # Idempotencia: INSERT OR IGNORE exigido por la prueba. Re-ejecutar el
            # scraper no duplica filas porque `municipio` es PRIMARY KEY.
            cursor.execute(
                "INSERT OR IGNORE INTO raw_registraduria (municipio, data_json) VALUES (?, ?)",
                (mun, json.dumps(data))
            )
            conn.commit()
            logging.info(f"Datos guardados en raw_registraduria para {mun}")
        else:
            logging.error(f"Sin datos para {mun}: ni API ni sample_data/ disponibles.")

    conn.close()
