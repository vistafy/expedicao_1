import sqlite3
from flask import current_app, g
from datetime import datetime

# 🔧 Adaptadores e conversores para TIMESTAMP
def adapt_datetime(ts):
    return ts.isoformat(" ")

def convert_datetime(s):
    try:
        return datetime.fromisoformat(s.decode())
    except Exception:
        return s

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

def get_db():
    """
    Abre uma conexão com o banco de dados SQLite e armazena em `g` (contexto da requisição).
    Se já existir uma conexão aberta, reutiliza.
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """
    Fecha a conexão com o banco ao final da requisição.
    É chamado automaticamente pelo `app.teardown_appcontext`.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()
