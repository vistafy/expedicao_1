from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from db import get_db

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

# 📌 Listar usuários (apenas admin)
@usuarios_bp.route("/", methods=["GET"])
@login_required
def lista():
    if not current_user.is_admin:
        flash("⛔ Acesso restrito ao administrador.", "erro")
        return redirect(url_for("dashboard.index"))

    conn = get_db()
    usuarios = conn.execute("""
        SELECT u.id, u.nome_completo, u.cpf, u.username, u.email, u.role, l.nome AS loja_nome
        FROM usuarios u
        LEFT JOIN lojas l ON u.loja_id = l.id
        ORDER BY u.id
    """).fetchall()

    return render_template("usuarios/lista.html", usuarios=usuarios)


# 📌 Criar novo usuário (apenas admin)
@usuarios_bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if not current_user.is_admin:
        flash("⛔ Acesso restrito ao administrador.", "erro")
        return redirect(url_for("dashboard.index"))

    conn = get_db()
    lojas = conn.execute("SELECT id, nome FROM lojas ORDER BY nome").fetchall()

    if request.method == "POST":
        nome_completo = request.form.get("nome_completo")
        cpf = request.form.get("cpf")
        username = request.form.get("username")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role", "user")
        loja_id = request.form.get("loja_id")

        # Normaliza CPF (remove pontos e traço)
        cpf_numeros = "".join([c for c in cpf if c.isdigit()]) if cpf else None

        if not nome_completo or not cpf_numeros or not username or not email or not senha:
            flash("⛔ Informe nome completo, CPF, usuário, email e senha.", "erro")
            return redirect(url_for("usuarios.novo"))

        if len(cpf_numeros) != 11:
            flash("⛔ CPF inválido. Digite no formato 000.000.000-00", "erro")
            return redirect(url_for("usuarios.novo"))

        if role == "user" and not loja_id:
            flash("⛔ Usuário comum precisa estar vinculado a uma loja.", "erro")
            return redirect(url_for("usuarios.novo"))

        existente = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
        if existente:
            flash("⛔ Usuário já existe.", "erro")
            return redirect(url_for("usuarios.novo"))

        senha_hash = generate_password_hash(senha)
        conn.execute(
            "INSERT INTO usuarios (nome_completo, cpf, username, email, senha, role, loja_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nome_completo, cpf_numeros, username, email, senha_hash, role, loja_id if role == "user" else None)
        )
        conn.commit()

        flash("✅ Usuário criado com sucesso!", "sucesso")
        return redirect(url_for("usuarios.lista"))

    return render_template("usuarios/novo.html", lojas=lojas)


# 📌 Editar usuário (apenas admin)
@usuarios_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id):
    if not current_user.is_admin:
        flash("⛔ Acesso restrito ao administrador.", "erro")
        return redirect(url_for("dashboard.index"))

    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id = ?", (id,)).fetchone()
    lojas = conn.execute("SELECT id, nome FROM lojas ORDER BY nome").fetchall()

    if not usuario:
        flash("⛔ Usuário não encontrado.", "erro")
        return redirect(url_for("usuarios.lista"))

    if request.method == "POST":
        nome_completo = request.form.get("nome_completo")
        cpf = request.form.get("cpf")
        username = request.form.get("username")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role", usuario["role"])
        loja_id = request.form.get("loja_id")

        cpf_numeros = "".join([c for c in cpf if c.isdigit()]) if cpf else usuario["cpf"]

        if not nome_completo or not cpf_numeros or not username or not email:
            flash("⛔ Nome completo, CPF, usuário e email não podem ficar vazios!", "erro")
        else:
            if senha:
                senha_hash = generate_password_hash(senha)
                conn.execute(
                    "UPDATE usuarios SET nome_completo = ?, cpf = ?, username = ?, email = ?, senha = ?, role = ?, loja_id = ? WHERE id = ?",
                    (nome_completo, cpf_numeros, username, email, senha_hash, role, loja_id if role == "user" else None, id)
                )
            else:
                conn.execute(
                    "UPDATE usuarios SET nome_completo = ?, cpf = ?, username = ?, email = ?, role = ?, loja_id = ? WHERE id = ?",
                    (nome_completo, cpf_numeros, username, email, role, loja_id if role == "user" else None, id)
                )
            conn.commit()
            flash("✅ Usuário atualizado com sucesso!", "sucesso")
            return redirect(url_for("usuarios.lista"))

    return render_template("usuarios/editar.html", usuario=usuario, lojas=lojas)


# 📌 Excluir usuário (apenas admin)
@usuarios_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
def excluir(id):
    if not current_user.is_admin:
        flash("⛔ Acesso restrito ao administrador.", "erro")
        return redirect(url_for("dashboard.index"))

    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id = ?", (id,)).fetchone()

    if not usuario:
        flash("⛔ Usuário não encontrado.", "erro")
    else:
        # 🚫 Impede que o admin se auto-exclua
        if usuario["role"] == "admin" and usuario["id"] == current_user.id:
            flash("⛔ Você não pode excluir sua própria conta de administrador.", "erro")
        else:
            conn.execute("DELETE FROM usuarios WHERE id = ?", (id,))
            conn.commit()
            flash("✅ Usuário excluído com sucesso!", "sucesso")

    return redirect(url_for("usuarios.lista"))
