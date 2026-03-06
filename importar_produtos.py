import psycopg2
import pandas as pd
from pathlib import Path

# 🔧 Configuração da conexão PostgreSQL
PG_CONN = {
    "dbname": "expedicao_1",
    "user": "postgres",
    "password": "rc04202894",  # troque pela sua senha real
    "host": "localhost",
    "port": "5432"
}

def inicializar_banco():
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()

    # Verifica se já existem registros
    cur.execute("SELECT COUNT(*) FROM produtos")
    total = cur.fetchone()[0]

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
            cur.execute("""
                INSERT INTO produtos (departamento, secao, descricao, gtin, produto)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (gtin) DO UPDATE
                SET departamento = EXCLUDED.departamento,
                    secao = EXCLUDED.secao,
                    descricao = EXCLUDED.descricao,
                    produto = EXCLUDED.produto
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

    cur.close()
    conn.close()


if __name__ == "__main__":
    inicializar_banco()
