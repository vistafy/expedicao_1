import sqlite3
import psycopg2
from psycopg2.extras import execute_batch

# Caminho do banco SQLite
SQLITE_DB = "instance/expedicao_1.db"

# Configuração do PostgreSQL
PG_CONN = {
    "dbname": "expedicao_1",
    "user": "postgres",
    "password": "rc04202894",
    "host": "localhost",
    "port": "5432"
}

def migrar_tabela(sqlite_conn, pg_conn, tabela):
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    # Pega todas as linhas da tabela no SQLite
    sqlite_cur.execute(f"SELECT * FROM {tabela}")
    rows = sqlite_cur.fetchall()

    # Pega nomes das colunas
    colunas = [desc[0] for desc in sqlite_cur.description]
    colunas_str = ", ".join(colunas)
    placeholders = ", ".join(["%s"] * len(colunas))

    # Monta comando de inserção no PostgreSQL com proteção contra duplicatas
    insert_sql = f"""
        INSERT INTO {tabela} ({colunas_str})
        VALUES ({placeholders})
        ON CONFLICT DO NOTHING
    """

    # Insere em lote (mais rápido)
    execute_batch(pg_cur, insert_sql, rows, page_size=1000)
    pg_conn.commit()

    print(f"✅ {len(rows)} registros migrados para {tabela}")

def main():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    pg_conn = psycopg2.connect(**PG_CONN)

    # Se já migrou algumas tabelas, pode comentar aqui para não repetir
    tabelas = [
        "lojas",
        "usuarios",
        "lotes",
        "lotes_lojas",
        "registros",
        "produtos",
        "reset_logs",
        "vendas",
        "avarias",
        "inventario_rotativo",
        "rotativos"
    ]

    for tabela in tabelas:
        migrar_tabela(sqlite_conn, pg_conn, tabela)

    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    main()
