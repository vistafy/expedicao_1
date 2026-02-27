import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join("instance", "expedicao_1.db")

def coluna_existe(cursor, tabela, coluna):
    cursor.execute(f"PRAGMA table_info({tabela});")
    colunas = [info[1] for info in cursor.fetchall()]
    return coluna in colunas

def migrar():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- MIGRAÇÃO USUÁRIOS ---
    if not coluna_existe(cursor, "usuarios", "email"):
        print("⚠️ Coluna 'email' não encontrada. Recriando tabela 'usuarios'...")

        cursor.execute("ALTER TABLE usuarios RENAME TO usuarios_old;")

        cursor.execute("""
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        INSERT INTO usuarios (id, username, email, senha, role, criado_em)
        SELECT id, username, '' as email, senha, 'user' as role, criado_em FROM usuarios_old;
        """)

        cursor.execute("DROP TABLE usuarios_old;")
        conn.commit()
        print("✅ Tabela 'usuarios' atualizada com colunas 'email' e 'role'.")
    else:
        print("✅ Coluna 'email' já existe. Nenhuma migração necessária.")

    # Atualiza usuário admin
    cursor.execute("""
    UPDATE usuarios
    SET email = ?, role = 'admin'
    WHERE username = ?
    """, ("romulo.oliveira@hiperdb.com.br", "admin"))

    # --- MIGRAÇÃO LOTES ---
    if not coluna_existe(cursor, "lotes", "usuario_id"):
        print("⚠️ Coluna 'usuario_id' não encontrada. Recriando tabela 'lotes'...")

        cursor.execute("ALTER TABLE lotes RENAME TO lotes_old;")

        cursor.execute("""
        CREATE TABLE lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            departamento TEXT NOT NULL,
            secao TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ativo',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
        );
        """)

        # Copia dados antigos e atribui admin (id=1) como criador padrão
        cursor.execute("""
        INSERT INTO lotes (id, usuario_id, departamento, secao, status, criado_em)
        SELECT id, 1 as usuario_id, departamento, secao, status, criado_em FROM lotes_old;
        """)

        cursor.execute("DROP TABLE lotes_old;")
        conn.commit()
        print("✅ Tabela 'lotes' atualizada com coluna 'usuario_id'.")
    else:
        print("✅ Coluna 'usuario_id' já existe. Nenhuma migração necessária.")

    conn.commit()
    conn.close()
    print("✅ Migração concluída.")

if __name__ == "__main__":
    migrar()
