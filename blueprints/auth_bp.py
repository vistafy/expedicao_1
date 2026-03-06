from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from db import get_cursor, get_db
from models import Usuario

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Serializer para tokens seguros
def get_serializer():
    return URLSafeTimedSerializer(current_app.secret_key)

# ---------------- LOGIN ----------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        senha = request.form.get("senha")

        cur = get_cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        row = cur.fetchone()

        if row and check_password_hash(row["senha"], senha):
            if row["status"] != "aprovado":
                flash("⛔ Seu cadastro ainda não foi aprovado pelo administrador.", "erro")
                return redirect(url_for("auth.login"))

            user = Usuario(
                id=row["id"],
                username=row["username"],
                email=row["email"],
                senha=row["senha"],
                role=row["role"],
                loja_id=row["loja_id"],
                criado_em=row["criado_em"],
                status=row["status"]
            )
            login_user(user)
            flash("✅ Login realizado com sucesso!", "sucesso")
            return redirect(url_for("index"))
        else:
            flash("⛔ Usuário ou senha inválidos.", "erro")
            return redirect(url_for("auth.login"))

    return render_template("auth/login.html")

# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("✅ Logout realizado com sucesso!", "sucesso")
    return redirect(url_for("index"))

# ---------------- REGISTRO ----------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    cur = get_cursor()
    cur.execute("SELECT id, nome FROM lojas ORDER BY nome")
    lojas = cur.fetchall()

    if request.method == "POST":
        nome_completo = request.form.get("nome_completo")
        cpf = request.form.get("cpf")
        loja_id = request.form.get("loja_id")
        username = request.form.get("username")
        email = request.form.get("email")
        senha = request.form.get("senha")
        confirmar_senha = request.form.get("confirmar_senha")

        if senha != confirmar_senha:
            flash("⛔ As senhas não coincidem.", "erro")
            return redirect(url_for("auth.register"))

        cpf_numeros = "".join([c for c in cpf if c.isdigit()])
        if len(cpf_numeros) != 11:
            flash("⛔ CPF inválido.", "erro")
            return redirect(url_for("auth.register"))

        role = "user"
        if role == "user" and not loja_id:
            flash("⛔ É obrigatório selecionar uma filial/loja.", "erro")
            return redirect(url_for("auth.register"))

        cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        row_user = cur.fetchone()
        cur.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        row_email = cur.fetchone()
        cur.execute("SELECT * FROM usuarios WHERE cpf = %s", (cpf_numeros,))
        row_cpf = cur.fetchone()

        if row_user or row_email or row_cpf:
            flash("⛔ Usuário, e-mail ou CPF já existe.", "erro")
            return redirect(url_for("auth.register"))

        senha_hash = generate_password_hash(senha)

        cur.execute(
            """
            INSERT INTO usuarios (nome_completo, cpf, loja_id, username, email, senha, role, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (nome_completo, cpf_numeros, loja_id if role == "user" else None,
             username, email, senha_hash, role, "pendente")
        )
        get_db().commit()

        flash("✅ Cadastro realizado! Aguarde aprovação do administrador.", "sucesso")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", lojas=lojas)

# ---------------- ESQUECEU SENHA ----------------
@auth_bp.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        cpf = request.form.get("cpf")
        email = request.form.get("email")

        cpf_numeros = "".join([c for c in cpf if c.isdigit()])
        if len(cpf_numeros) != 11:
            flash("⛔ CPF inválido.", "erro")
            return redirect(url_for("auth.forgot_password"))

        cur = get_cursor()
        cur.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        row = cur.fetchone()

        if not row:
            flash("⛔ CPF ou e-mail não encontrados.", "erro")
            return redirect(url_for("auth.forgot_password"))

        cpf_db = "".join([c for c in row["cpf"] if c.isdigit()])
        if cpf_numeros != cpf_db:
            flash("⛔ CPF ou e-mail não encontrados.", "erro")
            return redirect(url_for("auth.forgot_password"))

        serializer = get_serializer()
        token = serializer.dumps(email, salt="reset-senha")
        reset_url = url_for("auth.reset_password", token=token, _external=True)

        msg = Message("Redefinição de senha - Expedição_1", recipients=[email])
        msg.body = (
            f"Olá {row['nome_completo']}!\n\n"
            f"Clique no link para redefinir sua senha:\n{reset_url}\n\n"
            "Este link expira em 1 hora."
        )
        current_app.extensions['mail'].send(msg)

        flash("📧 Um link de redefinição foi enviado para seu e-mail.", "sucesso")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")

# ---------------- REDEFINIR SENHA ----------------
@auth_bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    serializer = get_serializer()
    try:
        email = serializer.loads(token, salt="reset-senha", max_age=3600)
    except SignatureExpired:
        flash("⛔ O link expirou. Solicite novamente.", "erro")
        return redirect(url_for("auth.forgot_password"))
    except BadSignature:
        flash("⛔ Link inválido.", "erro")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        nova_senha = request.form.get("senha")
        confirmar_senha = request.form.get("confirmar_senha")

        if nova_senha != confirmar_senha:
            flash("⛔ As senhas não coincidem.", "erro")
            return redirect(url_for("auth.reset_password", token=token))

        if len(nova_senha) < 6:
            flash("⛔ A senha deve ter pelo menos 6 caracteres.", "erro")
            return redirect(url_for("auth.reset_password", token=token))

        senha_hash = generate_password_hash(nova_senha)
        cur = get_cursor()
        cur.execute("UPDATE usuarios SET senha = %s WHERE email = %s", (senha_hash, email))

        cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            cur.execute("INSERT INTO reset_logs (usuario_id) VALUES (%s)", (row["id"],))

        get_db().commit()

        flash("✅ Senha redefinida com sucesso!", "sucesso")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
