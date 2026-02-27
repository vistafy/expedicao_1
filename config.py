import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

DB_PATH = os.path.join("instance", "expedicao_1.db")

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

def init_db():
    os.makedirs("instance", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()

    # Usuários
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_completo TEXT NOT NULL,
        cpf TEXT NOT NULL UNIQUE,
        loja_id INTEGER,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        senha TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pendente',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (
            (role = 'admin' AND loja_id IS NULL) OR
            (role = 'user' AND loja_id IS NOT NULL)
        ),
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE SET NULL
    )
    """)

    # Lotes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        status TEXT DEFAULT 'ativo',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )
    """)

    # Lojas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lojas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL UNIQUE,
        nome TEXT NOT NULL
    )
    """)

    # Relação lotes-lojas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lotes_lojas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote_id INTEGER NOT NULL,
        loja_id INTEGER NOT NULL,
        FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_lotes_lojas_unique
    ON lotes_lojas (lote_id, loja_id)
    """)

    # Registros
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote_id INTEGER NOT NULL,
        loja_id INTEGER NOT NULL,
        codigo TEXT,
        descricao TEXT,
        gtin TEXT,
        tara_kg REAL DEFAULT 0,
        peso_bruto_kg REAL DEFAULT 0,
        peso_liquido_kg REAL DEFAULT 0,
        quantidade INTEGER DEFAULT 0,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registros_lote_loja_codigo ON registros (lote_id, loja_id, codigo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registros_gtin ON registros (gtin)")

    # Produtos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        descricao TEXT NOT NULL,
        gtin TEXT UNIQUE,
        produto TEXT,
        data TEXT NOT NULL DEFAULT (date('now'))
    )
    """)

    # Índices para acelerar consultas por departamento e seção
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_departamento ON produtos(departamento)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_secao ON produtos(secao)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_departamento_secao ON produtos(departamento, secao)")

    # Logs de redefinição de senha
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reset_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        redefinido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )
    """)

    # Vendas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        loja_id INTEGER NOT NULL,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        codigo_interno INTEGER,
        gtin TEXT,
        produto TEXT,
        qtd_vendida REAL,
        venda REAL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_unique ON vendas (data, loja_id, codigo_interno, gtin)")

    # Avarias
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS avarias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        loja_id INTEGER NOT NULL,
        departamento TEXT,
        secao TEXT,
        codigo TEXT,
        gtin TEXT,
        quantidade REAL,
        custo_unitario REAL,
        valor REAL,
        descricao TEXT,
        usuario TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("DROP INDEX IF EXISTS idx_avarias_unique")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_avarias_data_loja ON avarias (data, loja_id)")

    # Inventário Rotativo
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventario_rotativo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        loja_id INTEGER NOT NULL,
        tipo_movimento TEXT,
        codigo_produto TEXT,
        gtin TEXT,
        produto TEXT,
        quantidade REAL,
        valor_total REAL,
        preco_medio REAL,
        curva TEXT,
        departamento TEXT,
        secao TEXT,
        grupo TEXT,
        subgrupo TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventario_loja_data ON inventario_rotativo (loja_id, data)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventario_departamento_secao ON inventario_rotativo (departamento, secao)")

    # Rotativos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rotativos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        loja_id INTEGER NOT NULL,
        tipo_movimento TEXT,
        codigo_produto TEXT,
        gtin TEXT,
        produto TEXT,
        quantidade REAL,
        valor_total REAL,
        preco_medio REAL,
        curva TEXT,
        departamento TEXT,
        secao TEXT,
        grupo TEXT,
        subgrupo TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rotativos_loja_data ON rotativos (loja_id, data)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rotativos_departamento_secao ON rotativos (departamento, secao)")

    # Inserir usuários de exemplo
    senha_admin = generate_password_hash("admin123")
    cursor.execute(
        "INSERT OR IGNORE INTO usuarios (nome_completo, cpf, username, email, senha, role, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Administrador do Sistema", "00000000000", "admin", "romulo.oliveira@hiperdb.com.br", senha_admin, "admin", "aprovado")
    )

    senha_romulo = generate_password_hash("senha")
    cursor.execute(
        "INSERT OR IGNORE INTO usuarios (nome_completo, cpf, username, email, senha, role, loja_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Rômulo Oliveira", "11111111111", "romulo", "romulo@expedicao.com", senha_romulo, "user", 1, "pendente")
    )

    # Inserir lojas de exemplo
    lojas_exemplo = [
        ("1", "Loja 1 - Teste"),
        ("17", "17 - HIPER BOA VISTA - G. Vargas"),
        ("29", "29 - SUPER RAIAR DO SOL"),
        ("30", "30 - SUPER J BEZERRA"),
        ("31", "31 - SUPER SANTA LUZIA"),
    ]
    for codigo, nome in lojas_exemplo:
        cursor.execute("INSERT OR IGNORE INTO lojas (codigo, nome) VALUES (?, ?)", (codigo, nome))

    conn.commit()
    conn.close()
    print(f"✅ Banco de dados inicializado com sucesso em {DB_PATH} (senhas criptografadas)")

    # --- Popular inventário rotativo automaticamente ---
    try:
        import inv_rot
        arquivo_inv = inv_rot.localizar_arquivo_inventario()
        if arquivo_inv:
            df_inv, linhas_descartadas, lojas_nome_map = inv_rot.processar_csv(arquivo_inv)
            inv_rot.salvar_no_banco(df_inv, linhas_descartadas, lojas_nome_map)
        print("📦 Inventário rotativo populado automaticamente")
    except Exception as e:
        print(f"⚠️ Erro ao popular inventário rotativo: {e}")

    # --- Popular rotativos automaticamente ---
    try:
        import rotativo
        arquivo_rot = rotativo.localizar_arquivo_rotativo()
        if arquivo_rot:
            df_rot, linhas_descartadas, lojas_nome_map = rotativo.processar_csv(arquivo_rot)
            rotativo.salvar_no_banco(df_rot, linhas_descartadas, lojas_nome_map)
        print("📦 Rotativos populados automaticamente")
    except Exception as e:
        print(f"⚠️ Erro ao popular rotativos: {e}")

if __name__ == "__main__":
    init_db()
