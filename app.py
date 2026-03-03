import os
import sys
from pathlib import Path
import pandas as pd
from flask import Flask, render_template
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash
from flask_mail import Mail

# Importar inicialização do banco e relatórios/avarias
from db import get_db, close_db
from config import init_db
from relatorios import salvar_tabela, localizar_relatorios_padrao, extrair_periodo, montar_tabela
from avarias import localizar_avarias_csv, montar_tabela_avarias, salvar_tabela_avarias

# 📌 Detectar base_dir para rodar como .py ou .exe
def base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)  # pasta temporária usada pelo PyInstaller
    return Path(__file__).parent

# 📌 Configuração do Flask com paths corretos
app = Flask(
    __name__,
    template_folder=str(base_dir() / "templates"),
    static_folder=str(base_dir() / "static"),
    instance_path=str(base_dir() / "instance")
)

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "chave_local_teste")
app.config['DATABASE'] = os.path.join(app.instance_path, 'expedicao_1.db')

os.makedirs(app.instance_path, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

# 📌 Classe de usuário para integração com Flask-Login
class Usuario(UserMixin):
    def __init__(self, id, username, email, senha, role, loja_id=None, criado_em=None, status="pendente"):
        self.id = id
        self.username = username
        self.email = email
        self.senha = senha
        self.role = role
        self.loja_id = loja_id
        self.criado_em = criado_em
        self.status = status

    def __repr__(self):
        return f"<Usuario id={self.id} username={self.username} role={self.role} loja_id={self.loja_id} status={self.status}>"

    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_user(self) -> bool:
        return self.role == "user"


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, email, senha, role, loja_id, criado_em, status FROM usuarios WHERE id = ?",
        (user_id,)
    ).fetchone()
    if row:
        return Usuario(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            senha=row["senha"],
            role=row["role"],
            loja_id=row["loja_id"],
            criado_em=row["criado_em"],
            status=row["status"]
        )
    return None

# 📌 Importar blueprints
from blueprints.lotes_bp import lotes_bp
from blueprints.usuarios_bp import usuarios_bp
from blueprints.auth_bp import auth_bp
from blueprints.dashboard_bp import dashboard_bp
from blueprints.admin_bp import admin_bp
from blueprints.analitico_bp import analitico_bp

app.register_blueprint(analitico_bp)
app.register_blueprint(lotes_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(admin_bp)

# 📌 Criar ou atualizar admin automaticamente
def criar_admin():
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE username = ?", ("admin",)).fetchone()
    senha_hash = generate_password_hash("admin123")

    if row is None:
        conn.execute(
            "INSERT INTO usuarios (nome_completo, cpf, username, email, senha, role, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Administrador do Sistema", "00000000000", "admin", "romulo.oliveira@hiperdb.com.br", senha_hash, "admin", "aprovado")
        )
        conn.commit()
        print("✅ Usuário admin criado")
    else:
        conn.execute("UPDATE usuarios SET senha = ?, role = 'admin', status = 'aprovado' WHERE username = ?", (senha_hash, "admin"))
        conn.commit()
        print("🔄 Usuário admin atualizado")

# 📌 Importar produtos automaticamente
def importar_produtos():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        descricao TEXT NOT NULL,
        gtin TEXT UNIQUE,
        produto TEXT
    )
    """)
    cursor = conn.execute("SELECT COUNT(*) FROM produtos")
    total = cursor.fetchone()[0]

    if total == 0:
        print("📌 Importando produtos do CSV...")
        caminho_csv = Path.home() / "Downloads" / "relatorio_estoque_geral.csv"
        if not caminho_csv.exists():
            print(f"❌ CSV não encontrado em {caminho_csv}")
            return

        df = pd.read_csv(caminho_csv, sep=";", encoding="latin1")
        df.columns = df.columns.str.strip()

        mapa_colunas = {
            "SeÃ§Ã£o": "Seção",
            "DescriÃ§Ã£o": "Descrição",
            "GTIN Principal": "GTIN",
            "Produto": "Produto",
            "Departamento": "Departamento"
        }
        df = df.rename(columns=mapa_colunas)

        colunas_interesse = ["Departamento", "Seção", "Descrição", "GTIN", "Produto"]
        colunas_existentes = [c for c in colunas_interesse if c in df.columns]

        if not colunas_existentes:
            print("❌ Nenhuma coluna esperada encontrada no CSV.")
            return

        dados = df[colunas_existentes].drop_duplicates().reset_index(drop=True)

        for _, row in dados.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO produtos (departamento, secao, descricao, gtin, produto)
                VALUES (?, ?, ?, ?, ?)
            """, (
                row.get("Departamento", "DESCONHECIDO"),
                row.get("Seção", "DESCONHECIDO"),
                row.get("Descrição", "DESCONHECIDO"),
                str(row.get("GTIN")) if pd.notna(row.get("GTIN")) else None,
                row.get("Produto", "DESCONHECIDO")
            ))
        conn.commit()
        print(f"✅ {len(dados)} produtos importados")
    else:
        print(f"📌 Banco já contém {total} produtos")

    conn.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.teardown_appcontext
def teardown_db(exception):
    close_db()

# 📌 Configuração segura usando variáveis de ambiente
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("MAIL_DEFAULT_SENDER")

mail = Mail(app)

# 📌 Inicializar banco sempre que o app subir (inclusive no Render/Gunicorn)
with app.app_context():
    init_db()
    criar_admin()
    importar_produtos()

if __name__ == "__main__":
    with app.app_context():
        # Relatórios e avarias só localmente (evita erro no Render por falta de CSVs)
        relatorios = localizar_relatorios_padrao()
        if relatorios:
            for arquivo in relatorios:
                periodo = extrair_periodo(arquivo)
                tabela = montar_tabela(arquivo, periodo)
                if not tabela.empty:
                    salvar_tabela(tabela)

        arquivos_avarias = localizar_avarias_csv()
        if arquivos_avarias:
            for arquivo in arquivos_avarias:
                tabela_avarias = montar_tabela_avarias(arquivo)
                if not tabela_avarias.empty:
                    salvar_tabela_avarias(tabela_avarias)

        print("🚀 Banco inicializado e relatórios/avarias repopulados")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=True)
