import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import linregress
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'puestos_2026.db')
OUTPUT_PATH = os.path.join(BASE_DIR, 'viz', 'scatter_ca_se.png')


def generate_scatter(db_path, output_path):
    conn = sqlite3.connect(db_path)
    query = """
        SELECT v.id_mesa, v.municipio,
               SUM(CASE WHEN c.corporacion = 'CA' THEN v.votos ELSE 0 END) as votos_ca,
               SUM(CASE WHEN c.corporacion = 'SE' THEN v.votos ELSE 0 END) as votos_se
        FROM votacion v
        JOIN candidatos c ON v.id_candidato = c.id_candidato
        GROUP BY v.id_mesa, v.municipio
        HAVING votos_ca > 0 AND votos_se > 0
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty or len(df) < 2:
        print("No hay suficientes datos para la regresion.")
        return

    slope, intercept, r_value, p_value, std_err = linregress(df['votos_ca'], df['votos_se'])

    # SALIDA ESTRICTA REQUERIDA POR LA PRUEBA TECNICA
    print(f"r={r_value:.3f} | pendiente={slope:.3f} | n_mesas={len(df)}")

    plt.figure(figsize=(10, 8))
    sns.scatterplot(data=df, x='votos_ca', y='votos_se', hue='municipio')

    x_vals = df['votos_ca']
    plt.plot(x_vals, intercept + slope * x_vals, color='red', label=f'OLS r={r_value:.3f}')

    plt.title('Relacion CA vs SE por Mesa')
    plt.xlabel('Votos Camara')
    plt.ylabel('Votos Senado')
    plt.legend()
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300)
    print(f"Scatter plot guardado en {output_path}")


if __name__ == "__main__":
    generate_scatter(DB_PATH, OUTPUT_PATH)
