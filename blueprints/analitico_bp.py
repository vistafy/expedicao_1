from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from db import get_db

analitico_bp = Blueprint("analitico", __name__, url_prefix="/analitico")

def format_brl(valor):
    return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

@analitico_bp.route("/", methods=["GET"])
@login_required
def analitico():
    conn = get_db()

    # Se for admin → todas as lojas
    if current_user.role == "admin":
        lojas = conn.execute("SELECT id, nome FROM lojas ORDER BY nome").fetchall()
        loja_id = request.args.get("loja")
        if not loja_id and lojas:
            loja_id = str(lojas[0]["id"])
    else:
        loja_id = str(current_user.loja_id)
        lojas = conn.execute(
            "SELECT id, nome FROM lojas WHERE id = ?", (loja_id,)
        ).fetchall()

    resumo = {}
    projecao = {}
    loja_nome = None
    departamentos = []
    secoes = []

    departamento_sel = request.args.get("departamento")
    secao_sel = request.args.get("secao")
    gtin_sel = request.args.get("gtin")
    codigo_sel = request.args.get("codigo")

    if loja_id:
        # Buscar nome da loja
        loja_row = conn.execute("SELECT nome FROM lojas WHERE id = ?", (loja_id,)).fetchone()
        if loja_row:
            loja_nome = loja_row["nome"]

        # Buscar departamentos e seções (somente para vendas)
        departamentos = conn.execute(
            "SELECT DISTINCT departamento FROM vendas WHERE loja_id = ? ORDER BY departamento",
            (loja_id,)
        ).fetchall()
        if departamento_sel:
            secoes = conn.execute(
                "SELECT DISTINCT secao FROM vendas WHERE loja_id = ? AND departamento = ? ORDER BY secao",
                (loja_id, departamento_sel)
            ).fetchall()

        # --- Vendas ---
        query_vendas = """
            SELECT SUM(venda)
            FROM vendas
            WHERE loja_id = ?
              AND substr(data, 4, 2) = strftime('%m', 'now')
              AND substr(data, 7, 4) = strftime('%Y', 'now')
        """
        params = [loja_id]
        if departamento_sel:
            query_vendas += " AND departamento = ?"
            params.append(departamento_sel)
        if secao_sel:
            query_vendas += " AND secao = ?"
            params.append(secao_sel)

        total_vendas = conn.execute(query_vendas, tuple(params)).fetchone()[0]
        resumo["vendas"] = format_brl(total_vendas or 0)

        dias_vendidos = conn.execute(
            """
            SELECT COUNT(DISTINCT substr(data, 1, 10))
            FROM vendas
            WHERE loja_id = ?
              AND substr(data, 4, 2) = strftime('%m', 'now')
              AND substr(data, 7, 4) = strftime('%Y', 'now')
            """,
            (loja_id,)
        ).fetchone()[0] or 1

        dias_total_mes = int(conn.execute(
            "SELECT strftime('%d', date('now','start of month','+1 month','-1 day'))"
        ).fetchone()[0])

        media_diaria = (total_vendas or 0) / dias_vendidos
        projecao["vendas"] = format_brl(media_diaria * dias_total_mes)

        # --- Avarias ---
        query_avarias = """
            SELECT SUM(valor)
            FROM avarias
            WHERE loja_id = ?
              AND strftime('%m', data) = strftime('%m', 'now')
              AND strftime('%Y', data) = strftime('%Y', 'now')
        """
        params_avarias = [loja_id]

        if departamento_sel:
            query_avarias += " AND departamento = ?"
            params_avarias.append(departamento_sel)
        if secao_sel:
            query_avarias += " AND secao = ?"
            params_avarias.append(secao_sel)
        if gtin_sel:
            query_avarias += " AND gtin = ?"
            params_avarias.append(gtin_sel)
        if codigo_sel:
            query_avarias += " AND codigo = ?"
            params_avarias.append(codigo_sel)

        total_avarias = conn.execute(query_avarias, tuple(params_avarias)).fetchone()[0]
        resumo["avarias"] = format_brl(total_avarias or 0)

        dias_avarias = conn.execute(
            """
            SELECT COUNT(DISTINCT date(data))
            FROM avarias
            WHERE loja_id = ?
              AND strftime('%m', data) = strftime('%m', 'now')
              AND strftime('%Y', data) = strftime('%Y', 'now')
            """,
            (loja_id,)
        ).fetchone()[0] or 1

        media_diaria_avarias = (total_avarias or 0) / dias_avarias
        projecao["avarias"] = format_brl(media_diaria_avarias * dias_total_mes)

        # --- Inventário (acumulado geral) ---
        query_inventario = """
            SELECT SUM(valor_total)
            FROM inventario_rotativo
            WHERE loja_id = ?
        """
        total_inventario = conn.execute(query_inventario, (loja_id,)).fetchone()[0]
        resumo["inventario"] = format_brl(total_inventario or 0)

        # --- Rotativos (acumulado geral) ---
        query_rotativos = """
            SELECT SUM(valor_total)
            FROM rotativos
            WHERE loja_id = ?
        """
        total_rotativos = conn.execute(query_rotativos, (loja_id,)).fetchone()[0]
        resumo["rotativos"] = format_brl(total_rotativos or 0)

        # --- Datas distintas para quadradinhos ---
        datas_inventario = [row[0] for row in conn.execute(
            """
            SELECT DISTINCT date(data)
            FROM inventario_rotativo
            WHERE loja_id = ?
            ORDER BY date(data)
            LIMIT 4
            """,
            (loja_id,)
        ).fetchall()]

        datas_rotativos = [row[0] for row in conn.execute(
            """
            SELECT DISTINCT date(data)
            FROM rotativos
            WHERE loja_id = ?
            ORDER BY date(data)
            LIMIT 4
            """,
            (loja_id,)
        ).fetchall()]

        return render_template(
            "analitico.html",
            lojas=lojas,
            loja_id=str(loja_id) if loja_id else None,
            loja_nome=loja_nome,
            resumo=resumo,
            projecao=projecao,
            departamentos=departamentos,
            secoes=secoes,
            departamento_sel=departamento_sel,
            secao_sel=secao_sel,
            gtin_sel=gtin_sel,
            codigo_sel=codigo_sel,
            datas_inventario=datas_inventario,
            datas_rotativos=datas_rotativos
        )

# --- Nova rota AJAX para atualizar valores dinamicamente ---
@analitico_bp.route("/valor", methods=["GET"])
@login_required
def valor_por_data():
    conn = get_db()
    loja_id = request.args.get("loja")
    tipo = request.args.get("tipo")  # inventario ou rotativos
    data_sel = request.args.get("data")

    departamento_sel = request.args.get("departamento")
    secao_sel = request.args.get("secao")
    gtin_sel = request.args.get("gtin")
    codigo_sel = request.args.get("codigo")

    if tipo == "inventario":
        query = """
            SELECT SUM(valor_total)
            FROM inventario_rotativo
            WHERE loja_id = ?
              AND date(data) = date(?)
        """
        params = [loja_id, data_sel]

    elif tipo == "rotativos":
        query = """
            SELECT SUM(valor_total)
            FROM rotativos
            WHERE loja_id = ?
              AND date(data) = date(?)
        """
        params = [loja_id, data_sel]
    else:
        return jsonify({"valor": "R$ 0,00"})

    # Aplicar filtros adicionais
    if departamento_sel and departamento_sel != "None":
        query += " AND departamento = ?"
        params.append(departamento_sel)
    if secao_sel and secao_sel != "None":
        query += " AND secao = ?"
        params.append(secao_sel)
    if gtin_sel and gtin_sel != "None":
        query += " AND gtin = ?"
        params.append(gtin_sel)
    if codigo_sel and codigo_sel != "None":
        query += " AND codigo_produto = ?"
        params.append(codigo_sel)

    total = conn.execute(query, tuple(params)).fetchone()[0]
    return jsonify({"valor": format_brl(total or 0)})
