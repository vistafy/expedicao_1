from flask import Blueprint, render_template
from flask_login import login_required
from db import get_db

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

def format_brl(valor):
    return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ",")

@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    conn = get_db()

    # Lotes ativos
    lotes_ativos = conn.execute(
        "SELECT COUNT(*) AS total FROM lotes WHERE status = 'ativo'"
    ).fetchone()["total"]

    # Total de registros
    total_registros = conn.execute(
        "SELECT COUNT(*) AS total FROM registros"
    ).fetchone()["total"]

    # Pesos por loja
    pesos_por_loja = conn.execute("""
        SELECT l.nome, SUM(r.peso_liquido_kg) AS total_peso
        FROM registros r
        JOIN lojas l ON r.loja_id = l.id
        GROUP BY l.nome
        ORDER BY total_peso DESC
    """).fetchall()

    # --- Avarias (mês atual) ---
    total_avarias = conn.execute(
        """
        SELECT SUM(valor) AS total
        FROM avarias
        WHERE strftime('%m', data) = strftime('%m', 'now')
          AND strftime('%Y', data) = strftime('%Y', 'now')
        """
    ).fetchone()["total"] or 0

    return render_template(
        "dashboard.html",
        lotes_ativos=lotes_ativos,
        total_registros=total_registros,
        pesos_por_loja=pesos_por_loja,
        total_avarias=format_brl(total_avarias)
    )
