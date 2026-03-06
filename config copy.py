import psycopg2
import os
from werkzeug.security import generate_password_hash

# 🔧 Configuração da conexão PostgreSQL
PG_CONN = {
    "dbname": "expedicao_1",
    "user": "postgres",
    "password": "rc04202894",  # troque pela sua senha
    "host": "localhost",
    "port": "5432"
}

def init_db():
    """
    Inicializa o banco PostgreSQL garantindo que as tabelas existam
    e popula dados básicos (admin, lojas de exemplo).
    """
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()

    # --- Criar usuário admin se não existir ---
    senha_admin = generate_password_hash("admin123")
    cur.execute("SELECT id FROM usuarios WHERE username = %s", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO usuarios (nome_completo, cpf, username, email, senha, role, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("Administrador do Sistema", "00000000000", "admin",
             "romulo.oliveira@hiperdb.com.br", senha_admin, "admin", "aprovado")
        )
        print("✅ Usuário admin criado")
    else:
        cur.execute(
            "UPDATE usuarios SET senha = %s, role = 'admin', status = 'aprovado' WHERE username = %s",
            (senha_admin, "admin")
        )
        print("🔄 Usuário admin atualizado")

    # --- Criar usuário de exemplo ---
    senha_romulo = generate_password_hash("senha")
    cur.execute("SELECT id FROM usuarios WHERE username = %s", ("romulo",))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO usuarios (nome_completo, cpf, username, email, senha, role, loja_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("Rômulo Oliveira", "11111111111", "romulo",
             "romulo@expedicao.com", senha_romulo, "user", 1, "pendente")
        )
        print("✅ Usuário romulo criado")

    # --- Inserir lojas de exemplo ---
    lojas_exemplo = [
        ("1", "Loja 1 - Teste"),
        ("17", "17 - HIPER BOA VISTA - G. Vargas"),
        ("29", "29 - SUPER RAIAR DO SOL"),
        ("30", "30 - SUPER J BEZERRA"),
        ("31", "31 - SUPER SANTA LUZIA"),
    ]
    for codigo, nome in lojas_exemplo:
        cur.execute("INSERT INTO lojas (codigo, nome) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (codigo, nome))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Banco PostgreSQL inicializado com usuários e lojas de exemplo")
