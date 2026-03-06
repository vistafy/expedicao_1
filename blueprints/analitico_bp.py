from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from db import get_cursor, get_db


analitico_bp = Blueprint("analitico", __name__, url_prefix="/analitico")

def format_brl(valor):
    return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

def format_kg(qtd):
    return "{:,.3f}".format(qtd).replace(",", "X").replace(".", ",").replace("X", ".") + " kg"

@analitico_bp.route("/", methods=["GET"])
@login_required
def analitico():
    conn = get_db()

    # Se for admin → todas as lojas
    if current_user.role == "admin":
        cur = get_cursor()
        cur.execute("SELECT id, nome FROM lojas ORDER BY nome")
        lojas = cur.fetchall()

        loja_id = request.args.get("loja")
        if not loja_id and lojas:
            loja_id = str(lojas[0]["id"])
    else:
        loja_id = str(current_user.loja_id)
        cur = get_cursor()
        cur.execute("SELECT id, nome FROM lojas WHERE id = %s", (loja_id,))
        lojas = cur.fetchall()


    resumo = {}
    projecao = {}
    loja_nome = None
    departamentos = []
    secoes = []

    departamento_sel = request.args.get("departamento")
    secao_sel = request.args.get("secao")
    gtin_sel = request.args.get("gtin")
    codigo_sel = request.args.get("codigo")
    mes_ano = request.args.get("mes_ano")

    # Se não vier mes_ano, usa mês atual
    if mes_ano:
        try:
            mes, ano = mes_ano.split("/")
        except Exception:
            cur = get_cursor()
            cur.execute("SELECT EXTRACT(MONTH FROM CURRENT_DATE) AS mes")
            mes = str(int(cur.fetchone()["mes"]))
            cur.execute("SELECT EXTRACT(YEAR FROM CURRENT_DATE) AS ano")
            ano = str(int(cur.fetchone()["ano"]))
    else:
        cur = get_cursor()
        cur.execute("SELECT EXTRACT(MONTH FROM CURRENT_DATE) AS mes")
        mes = str(int(cur.fetchone()["mes"]))
        cur.execute("SELECT EXTRACT(YEAR FROM CURRENT_DATE) AS ano")
        ano = str(int(cur.fetchone()["ano"]))

    if loja_id:
        # Buscar nome da loja
        cur.execute("SELECT nome FROM lojas WHERE id = %s", (loja_id,))
        loja_row = cur.fetchone()
        if loja_row:
            loja_nome = loja_row["nome"]

        # Buscar departamentos
        cur.execute(
            "SELECT DISTINCT departamento FROM vendas WHERE loja_id = %s ORDER BY departamento",
            (loja_id,)
        )
        departamentos = cur.fetchall()

        if departamento_sel:
            cur.execute(
                "SELECT DISTINCT secao FROM vendas WHERE loja_id = %s AND departamento = %s ORDER BY secao",
                (loja_id, departamento_sel)
            )
            secoes = cur.fetchall()

        # --- Vendas ---
        query_vendas = """
            SELECT COALESCE(SUM(venda),0)
            FROM vendas
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
        """

        params = [loja_id, ano, mes, ano, mes]
        if departamento_sel:
            query_vendas += " AND departamento = %s"
            params.append(departamento_sel)
        if secao_sel:
            query_vendas += " AND secao = %s"
            params.append(secao_sel)

        cur = get_cursor()
        cur.execute(query_vendas, tuple(params))
        total_vendas = cur.fetchone()[0] or 0
        resumo["vendas"] = format_brl(total_vendas)

        # Dias vendidos
        cur.execute(
            """
            SELECT COUNT(DISTINCT DATE(data)) AS dias
            FROM vendas
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
            """,
            (loja_id, ano, mes, ano, mes)
        )
        dias_vendidos = cur.fetchone()["dias"] or 1

        # Dias totais do mês
        cur.execute(
            """
            SELECT EXTRACT(DAY FROM (make_date(%s::int, %s::int, 1) 
                                    + INTERVAL '1 month - 1 day')) AS total_dias
            """,
            (ano, mes)
        )
        dias_total_mes = int(cur.fetchone()["total_dias"])

        # Média e projeção
        media_diaria = total_vendas / dias_vendidos if dias_vendidos else 0
        projecao["vendas"] = format_brl(media_diaria * dias_total_mes)

        # --- Avarias ---
        query_avarias = """
            SELECT COALESCE(SUM(valor),0)
            FROM avarias
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
        """

        params_avarias = [loja_id, ano, mes, ano, mes]
        if departamento_sel:
            query_avarias += " AND departamento = %s"
            params_avarias.append(departamento_sel)
        if secao_sel:
            query_avarias += " AND secao = %s"
            params_avarias.append(secao_sel)
        if gtin_sel:
            query_avarias += " AND gtin = %s"
            params_avarias.append(gtin_sel)
        if codigo_sel:
            query_avarias += " AND codigo = %s"
            params_avarias.append(codigo_sel)

        cur.execute(query_avarias, tuple(params_avarias))
        total_avarias = cur.fetchone()[0] or 0
        resumo["avarias"] = format_brl(total_avarias)

        # Dias com avarias
        cur.execute(
            """
            SELECT COUNT(DISTINCT DATE(data)) AS dias
            FROM avarias
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
            """,
            (loja_id, ano, mes, ano, mes)
        )
        dias_avarias = cur.fetchone()["dias"] or 1

        # Média e projeção
        media_diaria_avarias = total_avarias / dias_avarias if dias_avarias else 0
        projecao["avarias"] = format_brl(media_diaria_avarias * dias_total_mes)
        
        
        # --- Inventário (acumulado geral) ---
        query_inventario = """
            SELECT COALESCE(SUM(valor_total),0)
            FROM inventario_rotativo
            WHERE loja_id = %s
        """
        cur = get_cursor()

        # Inventário
        cur.execute(query_inventario, (loja_id,))
        total_inventario = cur.fetchone()[0] or 0
        resumo["inventario"] = format_brl(total_inventario)
        projecao["inventario"] = "R$ 0,00"

        # --- Rotativos (acumulado geral) ---
        query_rotativos = """
            SELECT COALESCE(SUM(valor_total),0)
            FROM rotativos
            WHERE loja_id = %s
        """
        cur.execute(query_rotativos, (loja_id,))
        total_rotativos = cur.fetchone()[0] or 0
        resumo["rotativos"] = format_brl(total_rotativos)
        projecao["rotativos"] = "R$ 0,00"

        # --- Datas distintas para quadradinhos ---
        cur.execute(
            """
            SELECT DISTINCT DATE(data) AS data
            FROM inventario_rotativo
            WHERE loja_id = %s
            ORDER BY DATE(data)
            LIMIT 4
            """,
            (loja_id,)
        )
        datas_inventario = [row["data"] for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT DATE(data) AS data
            FROM rotativos
            WHERE loja_id = %s
            ORDER BY DATE(data)
            LIMIT 4
            """,
            (loja_id,)
        )
        datas_rotativos = [row["data"] for row in cur.fetchall()]



        # --- Top 10 Vendas ---
        query_top_vendas = """
            SELECT codigo_interno AS codigo, produto AS descricao,
                SUM(qtd_vendida) AS quantidade, SUM(venda) AS venda
            FROM vendas
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
        """
        params_top_vendas = [loja_id, ano, mes, ano, mes]

        if departamento_sel:
            query_top_vendas += " AND departamento = %s"
            params_top_vendas.append(departamento_sel)
        if secao_sel:
            query_top_vendas += " AND secao = %s"
            params_top_vendas.append(secao_sel)

        query_top_vendas += """
            GROUP BY codigo_interno, produto
            ORDER BY venda DESC
            LIMIT 10
        """

        cur = get_cursor()
        cur.execute(query_top_vendas, tuple(params_top_vendas))
        top10_vendidos = [
            {
                "codigo": row["codigo"],
                "descricao": row["descricao"],
                "quantidade": format_kg(row["quantidade"]),
                "venda": format_brl(row["venda"])
            }
            for row in cur.fetchall()
        ]


        # --- Top 10 Avarias ---
        query_top_avarias = """
            SELECT codigo, descricao,
                SUM(quantidade) AS quantidade, SUM(valor) AS valor
            FROM avarias
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
        """
        params_top_avarias = [loja_id, ano, mes, ano, mes]

        if departamento_sel:
            query_top_avarias += " AND departamento = %s"
            params_top_avarias.append(departamento_sel)
        if secao_sel:
            query_top_avarias += " AND secao = %s"
            params_top_avarias.append(secao_sel)

        query_top_avarias += """
            GROUP BY codigo, descricao
            ORDER BY valor ASC   -- mostra os mais negativos primeiro
            LIMIT 10
        """

        cur = get_cursor()
        cur.execute(query_top_avarias, tuple(params_top_avarias))
        top10_avarias = [
            {
                "codigo": row["codigo"],
                "descricao": row["descricao"],
                "quantidade": format_kg(row["quantidade"]),
                "valor": format_brl(row["valor"])
            }
            for row in cur.fetchall()
        ]

        # --- Top 10 Inventário ---
        query_top_inventario = """
            SELECT DATE(data) AS data, codigo_produto AS codigo, produto AS descricao,
                SUM(quantidade) AS quantidade, SUM(valor_total) AS valor
            FROM inventario_rotativo
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
        """
        params_top_inventario = [loja_id, ano, mes, ano, mes]

        if departamento_sel:
            query_top_inventario += " AND departamento = %s"
            params_top_inventario.append(departamento_sel)
        if secao_sel:
            query_top_inventario += " AND secao = %s"
            params_top_inventario.append(secao_sel)

        query_top_inventario += """
            GROUP BY DATE(data), codigo_produto, produto
            ORDER BY valor ASC   -- mostra os mais negativos primeiro
            LIMIT 10
        """

        cur = get_cursor()
        cur.execute(query_top_inventario, tuple(params_top_inventario))
        top10_inventario = [
            {
                "data": row["data"],
                "codigo": row["codigo"],
                "descricao": row["descricao"],
                "quantidade": format_kg(row["quantidade"]),
                "valor": format_brl(row["valor"])
            }
            for row in cur.fetchall()
        ]


        # --- Top 10 Rotativos ---
        query_top_rotativos = """
            SELECT DATE(data) AS data, codigo_produto AS codigo, produto AS descricao,
                SUM(quantidade) AS quantidade, SUM(valor_total) AS valor
            FROM rotativos
            WHERE loja_id = %s
            AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                                AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
        """
        params_top_rotativos = [loja_id, ano, mes, ano, mes]

        if departamento_sel:
            query_top_rotativos += " AND departamento = %s"
            params_top_rotativos.append(departamento_sel)
        if secao_sel:
            query_top_rotativos += " AND secao = %s"
            params_top_rotativos.append(secao_sel)

        query_top_rotativos += """
            GROUP BY DATE(data), codigo_produto, produto
            ORDER BY valor ASC   -- mostra os mais negativos primeiro
            LIMIT 10
        """

        cur = get_cursor()
        cur.execute(query_top_rotativos, tuple(params_top_rotativos))
        top10_rotativos = [
            {
                "data": row["data"],
                "codigo": row["codigo"],
                "descricao": row["descricao"],
                "quantidade": format_kg(row["quantidade"]),
                "valor": format_brl(row["valor"])
            }
            for row in cur.fetchall()
        ]

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
            datas_rotativos=datas_rotativos,
            top10_vendidos=top10_vendidos,
            top10_avarias=top10_avarias,
            top10_inventario=top10_inventario,
            top10_rotativos=top10_rotativos
        )





# Função auxiliar para calcular totais
def calcular_total(base_query, params, filtros):
    query = base_query
    for campo, valor in filtros.items():
        if valor and valor != "None":
            query += f" AND {campo} = %s"
            params.append(valor)

    cur = get_cursor()
    cur.execute(query, tuple(params))
    return cur.fetchone()[0] or 0


# --- Rota AJAX para Inventário e Rotativos ---
@analitico_bp.route("/valor", methods=["GET"])
@login_required
def valor_por_data():
    loja_id = request.args.get("loja")
    tipo = request.args.get("tipo")  # inventario ou rotativos
    data_sel = request.args.get("data")

    filtros = {
        "departamento": request.args.get("departamento"),
        "secao": request.args.get("secao"),
        "gtin": request.args.get("gtin"),
        "codigo_produto": request.args.get("codigo"),
    }

    if tipo == "inventario":
        base_query = """
            SELECT COALESCE(SUM(valor_total),0)
            FROM inventario_rotativo
            WHERE loja_id = %s
              AND DATE(data) = %s::date
        """
    elif tipo == "rotativos":
        base_query = """
            SELECT COALESCE(SUM(valor_total),0)
            FROM rotativos
            WHERE loja_id = %s
              AND DATE(data) = %s::date
        """
    else:
        return jsonify({"valor": "R$ 0,00"})

    params = [loja_id, data_sel]
    total = calcular_total(base_query, params, filtros)
    return jsonify({"valor": format_brl(total)})


# --- Nova rota AJAX para Vendas ---
@analitico_bp.route("/vendas_valor", methods=["GET"])
@login_required
def vendas_valor():
    loja_id = request.args.get("loja")
    mes_ano = request.args.get("mes_ano")  # formato MM/YYYY

    try:
        mes, ano = mes_ano.split("/")
    except Exception:
        return jsonify({"valor": "R$ 0,00"})

    filtros = {
        "departamento": request.args.get("departamento"),
        "secao": request.args.get("secao"),
        "gtin": request.args.get("gtin"),
        "codigo_interno": request.args.get("codigo"),
    }

    base_query = """
        SELECT COALESCE(SUM(venda),0)
        FROM vendas
        WHERE loja_id = %s
          AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                             AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
    """
    params = [loja_id, ano, mes, ano, mes]
    total = calcular_total(base_query, params, filtros)
    return jsonify({"valor": format_brl(total)})


# --- Nova rota AJAX para Avarias ---
@analitico_bp.route("/avarias_valor", methods=["GET"])
@login_required
def avarias_valor():
    loja_id = request.args.get("loja")
    mes_ano = request.args.get("mes_ano")  # formato MM/YYYY

    try:
        mes, ano = mes_ano.split("/")
    except Exception:
        return jsonify({"valor": "R$ 0,00"})

    filtros = {
        "departamento": request.args.get("departamento"),
        "secao": request.args.get("secao"),
        "gtin": request.args.get("gtin"),
        "codigo": request.args.get("codigo"),
    }

    base_query = """
        SELECT COALESCE(SUM(valor),0)
        FROM avarias
        WHERE loja_id = %s
          AND DATE(data) BETWEEN make_date(%s::int, %s::int, 1)
                             AND (make_date(%s::int, %s::int, 1) + INTERVAL '1 month - 1 day')
    """
    params = [loja_id, ano, mes, ano, mes]
    total = calcular_total(base_query, params, filtros)
    return jsonify({"valor": format_brl(total)})
