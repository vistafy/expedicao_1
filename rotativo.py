from pathlib import Path
import pandas as pd
import sqlite3
import re

DB_PATH = "instance/expedicao_1.db"  # mesmo banco usado pelo init_db.py

def localizar_arquivo_rotativo():
    downloads = Path.home() / "Downloads"
    arquivo = downloads / "relatorio_movimentacao_inventario.csv"

    if arquivo.exists():
        print(f"✅ Arquivo encontrado: {arquivo}")
        return arquivo
    else:
        print("⚠️ Arquivo relatorio_movimentacao_inventario.csv não encontrado na pasta Downloads.")
        return None

def limpar_valores(df):
    def parse_valor(valor):
        if pd.isna(valor):
            return 0.0
        valor = str(valor).replace("R$", "").strip()
        negativo = "-" in valor or "–" in valor
        valor = re.sub(r"[^0-9,\.]", "", valor)
        if "," in valor and "." in valor:
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", ".")
        try:
            numero = float(valor)
            return -numero if negativo else numero
        except ValueError:
            return 0.0

    for col in ["quantidade", "valor_total", "preco_medio"]:
        if col not in df.columns:
            df[col] = 0.0

    df["quantidade"] = df["quantidade"].apply(parse_valor)
    df["valor_total"] = df["valor_total"].apply(parse_valor)
    df["preco_medio"] = df["preco_medio"].apply(parse_valor)
    return df

def processar_csv(arquivo):
    df = pd.read_csv(arquivo, sep=";", encoding="latin1")
    df.columns = df.columns.str.strip()

    mapa_colunas = {
        "Data Movimento": "data",
        "Loja": "loja",
        "Tipo de Movimento": "tipo_movimento",
        "Código do Produto": "codigo_produto",
        "CÃ³digo do Produto": "codigo_produto",
        "GTIN": "gtin",
        "Produto": "produto",
        "Quantidade": "quantidade",
        "Valor Total": "valor_total",
        "Preço Médio": "preco_medio",
        "PreÃ§o Medio": "preco_medio",
        "Curva": "curva",
        "Departamento": "departamento",
        "Seção": "secao",
        "SeÃ§Ã£o": "secao",
        "Grupo": "grupo",
        "Subgrupo": "subgrupo"
    }

    df = df.rename(columns=mapa_colunas)
    df = limpar_valores(df)

    df["data"] = df["data"].astype(str).str.strip()
    df["data"] = df["data"].str.replace(r"[^\d/]", "", regex=True)
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df.loc[df["data"].notna(), "data"] = df.loc[df["data"].notna(), "data"].dt.strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    lojas_map = {row[0]: row[1] for row in conn.execute("SELECT codigo, id FROM lojas").fetchall()}
    lojas_nome_map = {row[0]: row[1] for row in conn.execute("SELECT id, nome FROM lojas").fetchall()}
    conn.close()

    df["loja_codigo"] = df["loja"].astype(str).str.split("-").str[0].str.strip()
    df["loja_id"] = df["loja_codigo"].map(lojas_map)
    df = df.drop(columns=["loja", "loja_codigo"])

    total_linhas = len(df)
    df = df.dropna(subset=["data", "loja_id"])
    df["loja_id"] = df["loja_id"].astype(int)

    linhas_validas = len(df)
    linhas_descartadas = total_linhas - linhas_validas

    print(f"📊 Processadas: {total_linhas} | Inseridas: {linhas_validas} | Descartadas: {linhas_descartadas}")
    return df, linhas_descartadas, lojas_nome_map

def salvar_no_banco(df, linhas_descartadas, lojas_nome_map):
    conn = sqlite3.connect(DB_PATH)
    colunas_validas = [
        "data","loja_id","tipo_movimento","codigo_produto","gtin","produto",
        "quantidade","valor_total","preco_medio","curva","departamento","secao","grupo","subgrupo"
    ]

    df[colunas_validas].to_sql("rotativos", conn, if_exists="replace", index=False)
    conn.commit()

    resumo_lojas = df.groupby("loja_id")["valor_total"].sum().reset_index()
    conn.close()

    print("💾 Dados inseridos na tabela rotativos (SQLite).")
    print("🏬 Totais por loja (Rotativos):")
    for _, row in resumo_lojas.iterrows():
        loja_nome = lojas_nome_map.get(row["loja_id"], f"Loja {row['loja_id']}")
        print(f"- {loja_nome}: R$ {row['valor_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

if __name__ == "__main__":
    arquivo = localizar_arquivo_rotativo()
    if arquivo:
        df, linhas_descartadas, lojas_nome_map = processar_csv(arquivo)
        salvar_no_banco(df, linhas_descartadas, lojas_nome_map)
