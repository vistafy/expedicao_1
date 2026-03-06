import os
import psycopg2
import psycopg2.extras
from flask import g

def get_db():
    """
    Abre uma conexão com o banco PostgreSQL do Render usando DATABASE_URL.
    """
    if "db" not in g:
        db_url = os.environ.get("DATABASE_URL")
        g.db = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
        g.cur = g.db.cursor()
    return g.db

def get_cursor():
    """
    Retorna o cursor associado à conexão atual.
    """
    if "cur" not in g:
        get_db()
    return g.cur

def close_db(e=None):
    """
    Fecha a conexão com o banco ao final da requisição.
    """
    cur = g.pop("cur", None)
    if cur is not None:
        cur.close()

    db = g.pop("db", None)
    if db is not None:
        db.close()
