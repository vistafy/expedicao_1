from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from db import get_db
from decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 📌 Decorador para exigir admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if getattr(current_user, "role", None) != "admin":
            flash("⛔ Acesso restrito: apenas administradores podem visualizar este painel.", "erro")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function

# 📌 Painel principal
@admin_bp.route("/", methods=["GET"])
@login_required
@admin_required
def painel():
    return render_template("admin/index.html")

# 📌 Configurações
@admin_bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
@admin_required
def configuracoes():
    if request.method == "POST":
        tema = request.form.get("tema")
        email_notificacao = request.form.get("email_notificacao")

        # Exemplo fictício de salvar no banco
        # conn = get_db()
        # conn.execute("UPDATE configuracoes SET tema=?, email_notificacao=?", (tema, email_notificacao))
        # conn.commit()

        flash("✅ Configurações salvas com sucesso!", "sucesso")
        return redirect(url_for("admin.configuracoes"))

    return render_template("admin/configuracoes.html")

# 📌 Logs
@admin_bp.route("/logs", methods=["GET"])
@login_required
@admin_required
def logs():
    return render_template("admin/logs.html")

# 📌 Lista geral de usuários (CRUD)
@admin_bp.route("/usuarios", methods=["GET"])
@login_required
@admin_required
def usuarios():
    conn = get_db()
    usuarios = conn.execute(
        "SELECT id, nome_completo, email, username, loja_id, role, status FROM usuarios ORDER BY id"
    ).fetchall()
    return render_template("admin/usuarios.html", usuarios=usuarios)

# 📌 Aprovação de novos cadastros (somente pendentes)
@admin_bp.route("/aprovacoes", methods=["GET"])
@login_required
@admin_required
def aprovacoes():
    conn = get_db()
    usuarios_pendentes = conn.execute(
        "SELECT id, nome_completo, email, username, loja_id, role, status \
         FROM usuarios WHERE status = 'pendente' AND role = 'user' ORDER BY id"
    ).fetchall()
    return render_template("admin/aprovacoes.html", usuarios=usuarios_pendentes)

from db import get_cursor, get_db
from flask import redirect, url_for, flash
from flask_login import login_required
from decorators import admin_required

# 📌 Aprovar usuário
@admin_bp.route("/aprovacoes/aprovar/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def aprovar(user_id):
    cur = get_cursor()
    cur.execute("UPDATE usuarios SET status = 'aprovado' WHERE id = %s", (user_id,))
    get_db().commit()
    flash("✅ Usuário aprovado com sucesso!", "sucesso")
    return redirect(url_for("admin.aprovacoes"))

# 📌 Rejeitar usuário
@admin_bp.route("/aprovacoes/rejeitar/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def rejeitar(user_id):
    cur = get_cursor()
    cur.execute("UPDATE usuarios SET status = 'rejeitado' WHERE id = %s", (user_id,))
    get_db().commit()
    flash("❌ Usuário rejeitado.", "erro")
    return redirect(url_for("admin.aprovacoes"))
