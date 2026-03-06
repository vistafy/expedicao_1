from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required, current_user
from dados import atualizar_produtos_csv
import xlsxwriter
import io
from db import get_cursor, get_db
import pandas as pd
from pathlib import Path
from datetime import datetime


lotes_bp = Blueprint("lotes", __name__, url_prefix="/lotes")

# Função para carregar departamentos e seções do CSV
# Função para carregar departamentos e seções direto do banco
def carregar_departamentos_secoes_db():
    cur = get_cursor()

    # Buscar todos os departamentos
    cur.execute("SELECT DISTINCT departamento FROM produtos ORDER BY departamento")
    departamentos = [row["departamento"] for row in cur.fetchall()]

    # Buscar seções por departamento
    secoes_por_departamento = {}
    for dep in departamentos:
        cur.execute(
            "SELECT DISTINCT secao FROM produtos WHERE departamento = %s ORDER BY secao",
            (dep,)
        )
        secoes = [row["secao"] for row in cur.fetchall()]
        secoes_por_departamento[dep] = secoes

    return departamentos, secoes_por_departamento


# 📌 Listar lotes
@lotes_bp.route("/", methods=["GET"])
@login_required
def lotes():
    cur = get_cursor()

    if current_user.role == "admin":
        cur.execute("""
            SELECT lotes.*, usuarios.username AS criador
            FROM lotes
            JOIN usuarios ON lotes.usuario_id = usuarios.id
            ORDER BY lotes.criado_em DESC
        """)
    else:
        cur.execute("""
            SELECT lotes.*, usuarios.username AS criador
            FROM lotes
            JOIN usuarios ON lotes.usuario_id = usuarios.id
            WHERE lotes.usuario_id = %s
            ORDER BY lotes.criado_em DESC
        """, (current_user.id,))
    
    lotes = cur.fetchall()
    return render_template("lotes/lista.html", lotes=lotes)


# 📌 Exibir formulário de novo lote
@lotes_bp.route("/novo", methods=["GET"])
@login_required
def novo():
    departamentos, _ = carregar_departamentos_secoes_db()
    return render_template("lotes/novo_lote.html", departamentos=departamentos)

# 📌 Criar novo lote (POST)
@lotes_bp.route("/criar", methods=["POST"])
@login_required
def criar():
    departamento = request.form.get("departamento", "").strip()
    secao = request.form.get("secao", "").strip()

    if not departamento or not secao:
        flash("⛔ Informe departamento e seção.", "erro")
        return redirect(url_for("lotes.novo"))

    cur = get_cursor()
    # Agora vinculamos o lote ao usuário logado
    cur.execute("""
        INSERT INTO lotes (usuario_id, departamento, secao, status)
        VALUES (%s, %s, %s, 'ativo')
    """, (current_user.id, departamento, secao))
    get_db().commit()

    flash("✅ Lote criado com sucesso!", "sucesso")
    return redirect(url_for("lotes.lotes"))


# 📌 Rota auxiliar para AJAX: retorna seções de um departamento
@lotes_bp.route("/secoes/<departamento>")
@login_required
def secoes_por_departamento(departamento):
    cur = get_cursor()
    cur.execute(
        "SELECT DISTINCT secao FROM produtos WHERE departamento = %s ORDER BY secao",
        (departamento,)
    )
    secoes = [row["secao"] for row in cur.fetchall()]
    return jsonify(secoes)

# 📌 Selecionar lojas para um lote
@lotes_bp.route("/selecionar-lojas/<int:lote_id>", methods=["GET", "POST"])
@login_required
def selecionar_lojas(lote_id):
    cur = get_cursor()

    # Busca o lote e valida permissão
    cur.execute("SELECT * FROM lotes WHERE id = %s", (lote_id,))
    lote = cur.fetchone()
    if not lote or (current_user.role != "admin" and lote["usuario_id"] != current_user.id):
        flash("⛔ Você não tem permissão para acessar este lote.", "erro")
        return redirect(url_for("lotes.lotes"))

    if request.method == "POST":
        lojas_ids = request.form.getlist("lojas")

        # Remove vínculos antigos e insere os novos
        cur.execute("DELETE FROM lotes_lojas WHERE lote_id = %s", (lote_id,))
        for loja_id in lojas_ids:
            cur.execute(
                "INSERT INTO lotes_lojas (lote_id, loja_id) VALUES (%s, %s)",
                (lote_id, loja_id)
            )
        get_db().commit()

        flash("✅ Lojas vinculadas ao lote!", "sucesso")
        return redirect(url_for("lotes.lotes"))

    # Busca todas as lojas
    cur.execute("SELECT * FROM lojas ORDER BY codigo")
    lojas = cur.fetchall()

    # Busca lojas já vinculadas ao lote
    cur.execute("SELECT loja_id FROM lotes_lojas WHERE lote_id = %s", (lote_id,))
    vinculadas = cur.fetchall()
    vinculadas_ids = [str(v["loja_id"]) for v in vinculadas]  # 🔧 converte para string

    return render_template(
        "lotes/selecionar_lojas.html",
        lojas=lojas,
        vinculadas=vinculadas_ids,
        lote_id=lote_id
    )


@lotes_bp.route("/registrar", methods=["GET", "POST"])
@login_required
def registrar():
    cur = get_cursor()
    lote_id = request.args.get("id") or request.form.get("lote_id")

    if not lote_id:
        flash("⛔ Nenhum lote selecionado.", "erro")
        return redirect(url_for("lotes.lotes"))

    # Buscar informações do lote
    cur.execute("SELECT * FROM lotes WHERE id = %s", (lote_id,))
    lote = cur.fetchone()
    if not lote:
        flash("⛔ Lote não encontrado.", "erro")
        return redirect(url_for("lotes.lotes"))

    if request.method == "POST":
        acao = request.form.get("acao")
        codigo = request.form.get("codigo")
        descricao = request.form.get("descricao", "")
        gtin = request.form.get("gtin", "")
        tara = request.form.get("tara", "0").replace(",", ".")

        if acao == "registrar":
            if not (codigo or descricao or gtin):
                flash("⛔ Informe Código, Descrição ou GTIN do produto.", "erro")
                return redirect(url_for("lotes.registrar", id=lote_id))

            cur.execute("""
                SELECT l.id, l.codigo, l.nome
                FROM lotes_lojas ll
                JOIN lojas l ON ll.loja_id = l.id
                WHERE ll.lote_id = %s
            """, (lote_id,))
            lojas = cur.fetchall()

            for loja in lojas:
                peso = request.form.get(f"peso_{loja['id']}", "0").replace(",", ".")
                quantidade = request.form.get(f"quantidade_{loja['id']}", "0")

                try:
                    peso = float(peso)
                    tara = float(tara)
                    quantidade = int(quantidade or 0)
                except ValueError:
                    flash("⛔ Valores inválidos para peso ou quantidade.", "erro")
                    return redirect(url_for("lotes.registrar", id=lote_id))

                peso_liquido = max(0, peso - tara)

                cur.execute("""
                    SELECT id FROM registros
                    WHERE lote_id = %s AND loja_id = %s AND codigo = %s
                """, (lote_id, loja["id"], codigo))
                registro_existente = cur.fetchone()

                if registro_existente:
                    cur.execute("""
                        UPDATE registros
                        SET descricao = %s, gtin = %s, tara_kg = %s,
                            peso_bruto_kg = %s, peso_liquido_kg = %s, quantidade = %s
                        WHERE id = %s
                    """, (descricao, gtin, tara, peso, peso_liquido, quantidade, registro_existente["id"]))
                else:
                    cur.execute("""
                        INSERT INTO registros (lote_id, loja_id, codigo, descricao, gtin,
                                               tara_kg, peso_bruto_kg, peso_liquido_kg, quantidade)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (lote_id, loja["id"], codigo, descricao, gtin, tara, peso, peso_liquido, quantidade))

            get_db().commit()
            flash("✅ Produto registrado/atualizado com sucesso!", "sucesso")
            return redirect(url_for("lotes.registrar", id=lote_id))

        elif acao == "finalizar":
            cur.execute("UPDATE lotes SET status = 'finalizado' WHERE id = %s", (lote_id,))
            get_db().commit()
            flash("📦 Lote finalizado com sucesso!", "sucesso")
            return redirect(url_for("lotes.ver_lote", lote_id=lote_id))

    cur.execute("""
        SELECT l.id, l.codigo, l.nome
        FROM lotes_lojas ll
        JOIN lojas l ON ll.loja_id = l.id
        WHERE ll.lote_id = %s
    """, (lote_id,))
    lojas = cur.fetchall()

    return render_template("lotes/registrar.html", lote=lote, lote_id=lote_id, lojas=lojas)


# 📌 Ver detalhes de um lote
@lotes_bp.route("/ver/<int:lote_id>", methods=["GET"])
@login_required
def ver_lote(lote_id):
    cur = get_cursor()

    # Busca o lote e dados do usuário criador
    cur.execute("""
        SELECT l.*, u.username AS usuario_login, u.username AS usuario_nome
        FROM lotes l
        JOIN usuarios u ON l.usuario_id = u.id
        WHERE l.id = %s
    """, (lote_id,))
    lote = cur.fetchone()

    if not lote:
        flash("⛔ Lote não encontrado.", "erro")
        return redirect(url_for("lotes.lotes"))

    # Busca lojas vinculadas
    cur.execute("""
        SELECT nome FROM lojas
        JOIN lotes_lojas ON lojas.id = lotes_lojas.loja_id
        WHERE lotes_lojas.lote_id = %s
        ORDER BY lojas.codigo
    """, (lote_id,))
    lojas = cur.fetchall()
    lojas_nomes = [l["nome"] for l in lojas]

    # Busca registros do lote
    cur.execute("""
        SELECT r.*, lojas.nome AS loja
        FROM registros r
        JOIN lojas ON r.loja_id = lojas.id
        WHERE r.lote_id = %s
        ORDER BY r.codigo, r.loja_id
    """, (lote_id,))
    registros = cur.fetchall()

    # Agrupar registros por produto (código + descrição)
    agrupados = {}
    for r in registros:
        chave = f"{r['codigo']}|{r['descricao']}"
        agrupados.setdefault(chave, []).append(r)

    return render_template(
        "lotes/ver_lote.html",
        lote=lote,
        lojas=lojas_nomes,
        agrupados=agrupados,
        current_year=datetime.now().year
    )


# 📌 Finalizar lote
@lotes_bp.route("/finalizar/<int:lote_id>", methods=["POST", "GET"])
@login_required
def finalizar(lote_id):
    cur = get_cursor()

    # Atualiza status do lote
    cur.execute("UPDATE lotes SET status = 'finalizado' WHERE id = %s", (lote_id,))
    get_db().commit()

    flash("✅ Lote finalizado com sucesso!", "sucesso")
    return redirect(url_for("lotes.ver_lote", lote_id=lote_id))

# 📌 Exportar planilha por lote
@lotes_bp.route('/exportar_planilha')
@login_required
def exportar_planilha():
    lote_id = request.args.get('id')
    cur = get_cursor()

    # Busca seção do lote
    cur.execute("SELECT secao FROM lotes WHERE id = %s", (lote_id,))
    lote = cur.fetchone()

    # Busca registros do lote
    cur.execute("""
        SELECT r.codigo, r.descricao, l.nome AS loja, l.codigo AS loja_codigo, r.peso_liquido_kg
        FROM registros r
        JOIN lojas l ON r.loja_id = l.id
        WHERE r.lote_id = %s AND r.peso_bruto_kg > 0
        ORDER BY r.codigo, CAST(l.codigo AS INTEGER)
    """, (lote_id,))
    regs = cur.fetchall()

    # Converte para DataFrame
    df = pd.DataFrame([dict(r) for r in regs])
    if not df.empty:
        df["peso_liquido_kg"] = df["peso_liquido_kg"].round(3)

        # Coluna combinada para manter ordem numérica
        df["loja_coluna"] = df["loja_codigo"].astype(str) + " – " + df["loja"]

        # Pivot table
        tabela = df.pivot_table(
            index=["codigo", "descricao"],
            columns="loja_coluna",
            values="peso_liquido_kg",
            aggfunc="sum",
            fill_value=0
        )

        # Reordenar colunas numericamente
        tabela = tabela.reindex(
            sorted(tabela.columns, key=lambda x: int(x.split(" – ")[0])),
            axis=1
        )

        # Coluna de apontamento
        tabela["APONTAMENTO"] = tabela.sum(axis=1)
        tabela = tabela.reset_index().rename(columns={"codigo": "PLU"})

        headers = list(tabela.columns)
        data_rows = tabela.values.tolist()

        secao_nome = lote["secao"].replace(" ", "_") if lote else "Secao"
        sheet_name = f"EXPEDICAO_lote_{lote_id}_{secao_nome}"
        file_name = f"{sheet_name}.xlsx"

        # Cria arquivo Excel em memória
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(sheet_name)

        # Formatos
        num_format = workbook.add_format({'num_format': '#,##0.000'})
        l_format = workbook.add_format({'align': 'center', 'valign': 'vcenter'})

        # Cabeçalho
        worksheet.write_row(0, 0, headers)
        for col in range(len(headers)):
            worksheet.write(1, col, "l", l_format)

        # Dados
        for r_idx, row in enumerate(data_rows):
            for c_idx, val in enumerate(row):
                if isinstance(val, (int, float)):
                    worksheet.write(r_idx + 2, c_idx, float(val), num_format)
                else:
                    worksheet.write(r_idx + 2, c_idx, val)

        # Ajuste de largura
        worksheet.set_column(0, 0, 12)   # PLU
        worksheet.set_column(1, 1, 35)   # Descrição
        worksheet.set_column(2, len(headers)-1, 12, num_format)

        workbook.close()
        output.seek(0)

        return Response(
            output.read(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    # Caso não haja registros
    flash("⛔ Nenhum registro encontrado para este lote.", "erro")
    return redirect(url_for("lotes.lotes"))

# 📌 Excluir lote (com exclusão em cascata)
@lotes_bp.route("/excluir/<int:lote_id>", methods=["POST", "GET"])
@login_required
def excluir(lote_id):
    cur = get_cursor()

    # Excluir registros vinculados ao lote
    cur.execute("DELETE FROM registros WHERE lote_id = %s", (lote_id,))

    # Excluir vínculos de lojas com o lote
    cur.execute("DELETE FROM lotes_lojas WHERE lote_id = %s", (lote_id,))

    # Excluir o próprio lote
    cur.execute("DELETE FROM lotes WHERE id = %s", (lote_id,))

    get_db().commit()

    flash("🗑️ Lote e todos os registros associados foram excluídos com sucesso!", "sucesso")
    return redirect(url_for("lotes.lotes"))

# Autocommplete
@lotes_bp.route("/autocomplete/<int:lote_id>", methods=["GET"])
@login_required
def autocomplete(lote_id):
    termo = request.args.get("q", "").strip()
    cur = get_cursor()

    # Busca departamento e seção do lote atual
    cur.execute(
        "SELECT departamento, secao FROM lotes WHERE id = %s", 
        (lote_id,)
    )
    lote = cur.fetchone()

    if not lote:
        return jsonify([])

    # Filtra produtos apenas do mesmo departamento e seção
    cur.execute("""
        SELECT produto AS codigo, descricao, gtin
        FROM produtos
        WHERE departamento = %s AND secao = %s
          AND (produto LIKE %s OR descricao LIKE %s OR gtin LIKE %s)
        LIMIT 10
    """, (
        lote["departamento"],
        lote["secao"],
        f"%{termo}%",
        f"%{termo}%",
        f"%{termo}%"
    ))
    resultados = cur.fetchall()

    sugestoes = [
        {"codigo": r["codigo"], "descricao": r["descricao"], "gtin": r["gtin"]}
        for r in resultados
    ]
    return jsonify(sugestoes)

# 📌 API: buscar registros já existentes de um produto em um lote
@lotes_bp.route("/api/registro/<codigo>/<int:lote_id>", methods=["GET"])
@login_required
def api_registro(codigo, lote_id):
    cur = get_cursor()
    cur.execute("""
        SELECT loja_id, tara_kg AS tara, peso_bruto_kg AS peso, quantidade
        FROM registros
        WHERE lote_id = %s AND codigo = %s
    """, (lote_id, codigo))
    registros = cur.fetchall()

    resultado = [
        {
            "loja_id": r["loja_id"],
            "tara": r["tara"],
            "peso": r["peso"],
            "quantidade": r["quantidade"]
        }
        for r in registros
    ]
    return jsonify(resultado)


@lotes_bp.route("/atualizar-produtos", methods=["POST", "GET"])
@login_required
def atualizar_produtos():
    try:
        # chama a função que repopula a tabela produtos a partir do CSV
        atualizar_produtos_csv()
        flash("✅ Produtos atualizados com sucesso a partir do CSV!", "sucesso")
    except Exception as e:
        # captura qualquer erro e mostra mensagem amigável
        flash(f"⛔ Erro ao atualizar produtos: {str(e)}", "erro")
    # redireciona de volta para a lista de lotes
    return redirect(url_for("lotes.lotes"))
