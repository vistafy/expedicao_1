import sqlite3
import pandas as pd
from pathlib import Path

def inicializar_banco():
    conn = sqlite3.connect("instance/expedicao_1.db")

    # Cria tabela produtos se não existir, com gtin único
    conn.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        descricao TEXT NOT NULL,
        gtin TEXT UNIQUE,   -- garante que não haja duplicados
        produto TEXT
    )
    """)

    # Índices para acelerar consultas por departamento e seção
    conn.execute("CREATE INDEX IF NOT EXISTS idx_produtos_departamento ON produtos(departamento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_produtos_secao ON produtos(secao)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_produtos_departamento_secao ON produtos(departamento, secao)")

    # Verifica se já existem registros
    cursor = conn.execute("SELECT COUNT(*) FROM produtos")
    total = cursor.fetchone()[0]

    if total == 0:
        print("📌 Tabela 'produtos' vazia. Importando do CSV...")

        caminho_csv = Path.home() / "Downloads" / "relatorio_estoque_geral.csv"
        df = pd.read_csv(caminho_csv, sep=";", encoding="latin1")

        # Ajusta colunas
        df.columns = df.columns.str.strip()
        mapa_colunas = {
            "SeÃ§Ã£o": "Seção",
            "DescriÃ§Ã£o": "Descrição",
            "GTIN Principal": "GTIN",
            "Produto": "Produto",
            "Departamento": "Departamento"
        }
        df = df.rename(columns=mapa_colunas)

        # Seleciona apenas colunas de interesse
        colunas_interesse = ["Departamento", "Seção", "Descrição", "GTIN", "Produto"]
        dados = df[colunas_interesse].drop_duplicates().reset_index(drop=True)

        for _, row in dados.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO produtos (departamento, secao, descricao, gtin, produto)
                VALUES (?, ?, ?, ?, ?)
            """, (
                row.get("Departamento", "DESCONHECIDO"),
                row.get("Seção", "DESCONHECIDO"),
                row.get("Descrição", "DESCONHECIDO"),
                str(row.get("GTIN")) if pd.notna(row.get("GTIN")) else None,
                row.get("Produto", "DESCONHECIDO")
            ))

        conn.commit()
        print(f"✅ {len(dados)} produtos importados com sucesso!")
    else:
        print(f"📌 Banco já contém {total} produtos. Nenhuma importação necessária.")

    conn.close()


if __name__ == "__main__":
    inicializar_banco()
