-- Tabela de usuários
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_completo TEXT NOT NULL,
    cpf TEXT UNIQUE NOT NULL,
    loja_id INTEGER,                     -- chave estrangeira para tabela lojas
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',   -- 'admin' ou 'user'
    status TEXT NOT NULL DEFAULT 'pendente', -- 'pendente', 'aprovado', 'rejeitado'
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (role = 'admin' AND loja_id IS NULL) OR
        (role = 'user' AND loja_id IS NOT NULL)
    ),
    FOREIGN KEY (loja_id) REFERENCES lojas (id) ON DELETE SET NULL
);

-- Tabela de lojas
CREATE TABLE IF NOT EXISTS lojas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL
);

-- Tabela de lotes
CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    departamento TEXT NOT NULL,
    secao TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ativo',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

-- Relação entre lotes e lojas
CREATE TABLE IF NOT EXISTS lotes_lojas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id INTEGER NOT NULL,
    loja_id INTEGER NOT NULL,
    FOREIGN KEY (lote_id) REFERENCES lotes (id) ON DELETE CASCADE,
    FOREIGN KEY (loja_id) REFERENCES lojas (id) ON DELETE CASCADE
);

-- Índice único para evitar duplicatas de vínculos
CREATE UNIQUE INDEX IF NOT EXISTS idx_lotes_lojas_unique
ON lotes_lojas (lote_id, loja_id);

-- Registros de produtos em lotes
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id INTEGER NOT NULL,
    loja_id INTEGER NOT NULL,
    codigo TEXT,                -- pode ser nulo se usar descricao ou gtin
    descricao TEXT,
    gtin TEXT,                  -- padronizado como TEXT
    tara_kg REAL DEFAULT 0,
    peso_bruto_kg REAL DEFAULT 0,
    peso_liquido_kg REAL DEFAULT 0,
    quantidade INTEGER DEFAULT 0,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lote_id) REFERENCES lotes (id) ON DELETE CASCADE,
    FOREIGN KEY (loja_id) REFERENCES lojas (id) ON DELETE CASCADE
);

-- Índices para acelerar buscas
CREATE INDEX IF NOT EXISTS idx_registros_lote_loja_codigo
ON registros (lote_id, loja_id, codigo);

CREATE INDEX IF NOT EXISTS idx_registros_gtin
ON registros (gtin);

-- Produtos
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    departamento TEXT NOT NULL,
    secao TEXT NOT NULL,
    descricao TEXT NOT NULL,
    gtin TEXT UNIQUE,   -- padronizado como TEXT
    produto TEXT,
    data TEXT NOT NULL DEFAULT (date('now'))  -- nova coluna de data, formato YYYY-MM-DD
);



-- Logs de redefinição de senha
CREATE TABLE IF NOT EXISTS reset_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    redefinido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

-- Vendas
CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    loja_id INTEGER NOT NULL,   -- chave estrangeira para tabela lojas
    departamento TEXT NOT NULL,
    secao TEXT NOT NULL,
    codigo_interno INTEGER,
    gtin TEXT,                  -- corrigido para TEXT
    produto TEXT,
    qtd_vendida REAL,
    venda REAL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (loja_id) REFERENCES lojas (id) ON DELETE CASCADE
);

-- Índice único para evitar duplicatas em vendas
CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_unique
ON vendas (data, loja_id, codigo_interno, gtin);

-- Avarias
CREATE TABLE IF NOT EXISTS avarias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,                 -- salvar como YYYY-MM-DD
    loja_id INTEGER NOT NULL,           -- chave estrangeira para tabela lojas
    departamento TEXT,
    secao TEXT,
    codigo TEXT,
    gtin TEXT,
    quantidade REAL,
    custo_unitario REAL,
    valor REAL,
    descricao TEXT,                     -- incluída para compatibilidade com avarias.py
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (loja_id) REFERENCES lojas (id) ON DELETE CASCADE
);

-- Índice normal (não único) para acelerar buscas em avarias
CREATE INDEX IF NOT EXISTS idx_avarias_data_loja
ON avarias (data, loja_id);

-- Inventário Rotativo
CREATE TABLE IF NOT EXISTS inventario_rotativo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,          -- formato YYYY-MM-DD
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
);

-- Índices para acelerar buscas
CREATE INDEX IF NOT EXISTS idx_inventario_loja_data
ON inventario_rotativo (loja_id, data);

CREATE INDEX IF NOT EXISTS idx_inventario_departamento_secao
ON inventario_rotativo (departamento, secao);


-- Rotativos (apenas movimentos do tipo Rotativo)
CREATE TABLE IF NOT EXISTS rotativos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,          -- formato YYYY-MM-DD
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
);

-- Índices para acelerar buscas
CREATE INDEX IF NOT EXISTS idx_rotativos_loja_data
ON rotativos (loja_id, data);

CREATE INDEX IF NOT EXISTS idx_rotativos_departamento_secao
ON rotativos (departamento, secao);
