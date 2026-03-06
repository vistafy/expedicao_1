from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from db import get_cursor, get_db

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

# 📌 Listar usuários (apenas admin)
@usuarios_bp.route("/", methods=["GET"])
@login_required
def lista():
    if not current_user.is_admin:
        flash("⛔ Acesso restrito ao administrador.", "erro")
        return redirect(url_for("dashboard.index"))

    cur = get_cursor()
    cur.execute("""
        SELECT u.id, u.nome_completo, u.cpf, u.username, u.email, u.role, l.nome AS loja_nome
        FROM usuarios u
        LEFT JOIN lojas l ON u.loja_id = l.id
        ORDER BY u.id
    """)
    usuarios = cur.fetchall()

    return render_template("usuarios/lista.html", usuarios=usuarios)

# 📌 Criar novo usuário (apenas admin)
@usuarios_bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if not current_user.is_admin:
        flash("⛔ Acesso restrito ao administrador.", "erro")
        return redirect(url_for("dashboard.index"))

    cur = get_cursor()
    cur.execute("SELECT id, nome FROM lojas ORDER BY nome")
    lojas = cur.fetchall()

    if request.method == "POST":
        nome_completo = request.form.get("nome_completo")
        cpf = request.form.get("cpf")
        username = request.form.get("username")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role", "user")
        loja_id = request.form.get("loja_id")

        cpf_numeros = "".join([c for c in cpf if c.isdigit()]) if cpf else None

        if not nome_completo or not cpf_numeros or not username or not email or not senha:
            flash("⛔ Informe nome completo, CPF, usuário, email e senha.", "erro")
            return redirect(url_for("usuarios.novo"))

        if len(cpf_numeros) != 11:
            flash("⛔ CPF inválido.", "erro")
            return redirect(url_for("usuarios.novo"))

        if role == "user" and not loja_id:
            flash("⛔ Usuário comum precisa estar vinculado a uma loja.", "erro")
            return redirect(url_for("usuarios.novo"))

        cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        existente = cur.fetchone()
        if existente:
            flash("⛔ Usuário já existe.", "erro")
            return redirect(url_for("usuarios.novo"))

        senha_hash = generate_password_hash(senha)
        cur.execute(
            """
            INSERT INTO usuarios (nome_completo, cpf, username, email, senha, role, loja_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (nome_completo, cpf_numeros, username, email, senha_hash, role, loja_id if role == "user" else None)
        )
        get_db().commit()

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

    cur = get_cursor()
    cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cur.fetchone()
    cur.execute("SELECT id, nome FROM lojas ORDER BY nome")
    lojas = cur.fetchall()

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
                cur.execute(
                    """
                    UPDATE usuarios
                    SET nome_completo = %s, cpf = %s, username = %s, email = %s,
                        senha = %s, role = %s, loja_id = %s
                    WHERE id = %s
                    """,
                    (nome_completo, cpf_numeros, username, email, senha_hash,
                     role, loja_id if role == "user" else None, id)
                )
            else:
                cur.execute(
                    """
                    UPDATE usuarios
                    SET nome_completo = %s, cpf = %s, username = %s, email = %s,
                        role = %s, loja_id = %s
                    WHERE id = %s
                    """,
                    (nome_completo, cpf_numeros, username, email,
                     role, loja_id if role == "user" else None, id)
                )
            get_db().commit()
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

    cur = get_cursor()
    cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cur.fetchone()

    if not usuario:
        flash("⛔ Usuário não encontrado.", "erro")
    else:
        if usuario["role"] == "admin" and usuario["id"] == current_user.id:
            flash("⛔ Você não pode excluir sua própria conta de administrador.", "erro")
        else:
            cur.execute("DELETE FROM usuarios WHERE id = %s", (id,))
            get_db().commit()
            flash("✅ Usuário excluído com sucesso!", "sucesso")

    return redirect(url_for("usuarios.lista"))
