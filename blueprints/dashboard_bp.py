from flask import Blueprint, render_template
from flask_login import login_required
from db import get_cursor
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

def format_brl(valor):
    return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ",")

@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    cur = get_cursor()

    # Lotes ativos
    cur.execute("SELECT COUNT(*) AS total FROM lotes WHERE status = 'ativo'")
    lotes_ativos = cur.fetchone()["total"]

    # Total de registros
    cur.execute("SELECT COUNT(*) AS total FROM registros")
    total_registros = cur.fetchone()["total"]

    # Pesos por loja
    cur.execute("""
        SELECT l.nome, SUM(r.peso_liquido_kg) AS total_peso
        FROM registros r
        JOIN lojas l ON r.loja_id = l.id
        GROUP BY l.nome
        ORDER BY total_peso DESC
    """)
    pesos_por_loja = cur.fetchall()

    # --- Avarias (mês atual) ---
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM avarias
        WHERE EXTRACT(MONTH FROM data) = EXTRACT(MONTH FROM CURRENT_DATE)
          AND EXTRACT(YEAR FROM data) = EXTRACT(YEAR FROM CURRENT_DATE)
    """)
    total_avarias = cur.fetchone()["total"]

    return render_template(
        "dashboard.html",
        lotes_ativos=lotes_ativos,
        total_registros=total_registros,
        pesos_por_loja=pesos_por_loja,
        total_avarias=format_brl(total_avarias)
    )
