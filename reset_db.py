import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join("instance", "expedicao_1.db")

def reset_db():
    # Apagar banco antigo
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🗑️ Banco antigo removido.")

    os.makedirs("instance", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Recriar tabelas
    cursor.executescript("""
    CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        senha TEXT NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        status TEXT DEFAULT 'ativo',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE lojas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL UNIQUE,
        nome TEXT NOT NULL
    );

    CREATE TABLE lotes_lojas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote_id INTEGER NOT NULL,
        loja_id INTEGER NOT NULL,
        FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    );

    CREATE TABLE registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote_id INTEGER NOT NULL,
        loja_id INTEGER NOT NULL,
        codigo TEXT NOT NULL,
        descricao TEXT,
        tara_kg REAL DEFAULT 0,
        peso_bruto_kg REAL DEFAULT 0,
        peso_liquido_kg REAL DEFAULT 0,
        quantidade INTEGER DEFAULT 0,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    );
    """)

    # Inserir usuários iniciais
    senha_admin = generate_password_hash("admin123")
    cursor.execute("INSERT INTO usuarios (username, senha) VALUES (?, ?)", ("admin", senha_admin))

    senha_romulo = generate_password_hash("senha")
    cursor.execute("INSERT INTO usuarios (username, senha) VALUES (?, ?)", ("romulo", senha_romulo))

    # Inserir lojas de exemplo
    lojas_exemplo = [
        ("001", "DB Supermercados - Centro"),
        ("002", "DB Supermercados - Norte"),
        ("003", "DB Supermercados - Sul"),
        ("004", "DB Supermercados - Leste"),
    ]
    cursor.executemany("INSERT INTO lojas (codigo, nome) VALUES (?, ?)", lojas_exemplo)

    conn.commit()
    conn.close()
    print("✅ Banco recriado com sucesso em", DB_PATH)

if __name__ == "__main__":
    reset_db()
