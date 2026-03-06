import psycopg2
import psycopg2.extras
from flask import g

# 🔧 Configuração da conexão PostgreSQL
PG_CONN = {
    "dbname": "expedicao_1",
    "user": "postgres",
    "password": "rc04202894",  # troque pela sua senha real
    "host": "localhost",
    "port": "5432"
}

def get_db():
    """
    Abre uma conexão com o banco de dados PostgreSQL e armazena em `g` (contexto da requisição).
    Se já existir uma conexão aberta, reutiliza.
    """
    if "db" not in g:
        g.db = psycopg2.connect(**PG_CONN)
        # Cursor que retorna resultados como dicionário (similar ao sqlite3.Row)
        g.cur = g.db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    return g.db

def get_cursor():
    """
    Retorna o cursor associado à conexão atual.
    """
    if "cur" not in g:
        get_db()  # garante que a conexão está aberta
    return g.cur

def close_db(e=None):
    """
    Fecha a conexão com o banco ao final da requisição.
    É chamado automaticamente pelo `app.teardown_appcontext`.
    """
    cur = g.pop("cur", None)
    if cur is not None:
        cur.close()

    db = g.pop("db", None)
    if db is not None:
        db.close()
