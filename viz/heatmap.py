import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'puestos_2026.db')
OUTPUT_PATH = os.path.join(BASE_DIR, 'viz', 'heatmap_municipios.png')


def generate_heatmap(db_path, output_path):
    conn = sqlite3.connect(db_path)
    query = """
        SELECT c.nombre_normalizado as candidato, v.municipio, SUM(v.votos) as votos
        FROM votacion v
        JOIN candidatos c ON v.id_candidato = c.id_candidato
        WHERE c.corporacion = 'CA'
        GROUP BY c.nombre_normalizado, v.municipio
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("No hay datos para generar el Heatmap.")
        return

    # Total real de votos CA por municipio (todos los candidatos, no solo el
    # top 8) para que el porcentaje mostrado sea "% del total del municipio"
    # y no "% del subtotal de los 8 candidatos filtrados".
    total_por_municipio = df.groupby('municipio')['votos'].sum()

    top_8 = df.groupby('candidato')['votos'].sum().nlargest(8).index
    df_top = df[df['candidato'].isin(top_8)]

    pivot_df = df_top.pivot_table(index='candidato', columns='municipio', values='votos', aggfunc='sum').fillna(0)
    pivot_pct = pivot_df.div(total_por_municipio, axis=1) * 100

    plt.figure(figsize=(12, 8))
    sns.heatmap(pivot_pct, annot=True, fmt=".1f", cmap="Blues")
    plt.title('Porcentaje de Votos CA por Municipio (Top 8 Candidatos)')
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300)
    print(f"Heatmap guardado en {output_path}")


if __name__ == "__main__":
    generate_heatmap(DB_PATH, OUTPUT_PATH)
