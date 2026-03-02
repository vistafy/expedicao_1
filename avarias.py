import re
import pandas as pd
from pathlib import Path
import sqlite3
import locale
from datetime import datetime

# Configura locale para Brasil
try:
    locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
except:
    locale.setlocale(locale.LC_ALL, "")

DB_PATH = "instance/expedicao_1.db"

def get_downloads_folder():
    return Path.home() / "Downloads"

def localizar_avarias_csv():
    pasta_downloads = get_downloads_folder()
    padrao = re.compile(r"^relatorio_analitico_de_trocas(\s*\(\d+\))?\.csv$", re.IGNORECASE)
    return [f for f in pasta_downloads.iterdir() if f.is_file() and padrao.match(f.name)]

def parse_data(x):
    """Converte datas para formato YYYY-MM-DD, aceitando dd/mm/yyyy ou yyyy-mm-dd"""
    x = str(x).strip()
    if not x or x.lower() == "nan":
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(x, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def montar_tabela_avarias(arquivo):
    try:
        df = pd.read_csv(arquivo, sep=";", encoding="latin1")
        df.columns = df.columns.str.strip()
        print("📑 Cabeçalho do CSV:", df.columns.tolist())

        mapa_colunas = {
            "Loja": "loja_codigo",
            "Data": "data",
            "CÃ³digo Interno": "codigo",
            "Código Interno": "codigo",
            "Descrição": "descricao",
            "DescriÃ§Ã£o": "descricao",
            "Quantidade": "quantidade",
            "Custo Estoque de Venda (UN)": "custo_unitario",
            "Total Custo Estoque de Venda": "valor",
            "Usuário": "usuario",
            "UsuÃ¡rio": "usuario",
            "GTIN": "gtin",
            "GTIN/PLU": "gtin"
        }
        df = df.rename(columns={k: v for k, v in mapa_colunas.items() if k in df.columns})

        for col in ["codigo", "descricao", "usuario", "gtin"]:
            if col not in df.columns:
                df[col] = ""

        # Conversão de valores numéricos
        for col in ["quantidade", "custo_unitario", "valor"]:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(r"R\$", "", regex=True)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False)
                    .str.strip()
                )
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Conversão da coluna data para YYYY-MM-DD
        df["data"] = df["data"].apply(parse_data)

        return df

    except Exception as e:
        print(f"❌ Erro ao montar tabela de avarias: {e}")
        return pd.DataFrame()

def salvar_tabela_avarias(df):
    if df.empty:
        print("⚠️ Nenhum dado para salvar.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Garantir tabelas
    conn.execute("""
    CREATE TABLE IF NOT EXISTS lojas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE,
        nome TEXT
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS avarias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        loja_id INTEGER,
        departamento TEXT,
        secao TEXT,
        codigo TEXT,
        gtin TEXT,
        quantidade REAL,
        custo_unitario REAL,
        valor REAL,
        descricao TEXT,
        usuario TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)

    # --- Carregar produtos em memória ---
    produtos_df = pd.read_sql_query(
        "SELECT gtin, produto, departamento, secao FROM produtos", conn
    )

    # Garantir que os campos usados no merge sejam strings
    df["codigo"] = df["codigo"].astype(str).str.strip()
    df["gtin"] = df["gtin"].astype(str).str.strip()
    df["loja_codigo"] = df["loja_codigo"].astype(str).str.strip()

    produtos_df["produto"] = produtos_df["produto"].astype(str).str.strip()
    produtos_df["gtin"] = produtos_df["gtin"].astype(str).str.strip()

    # Merge por GTIN
    df = df.merge(produtos_df, how="left", left_on="gtin", right_on="gtin")

    # Merge por código interno (produto)
    df = df.merge(produtos_df, how="left", left_on="codigo", right_on="produto", suffixes=("", "_by_codigo"))

    # Escolher departamento/secao (prioridade: GTIN → código interno)
    df["departamento_final"] = df["departamento"].combine_first(df["departamento_by_codigo"])
    df["secao_final"] = df["secao"].combine_first(df["secao_by_codigo"])

    # --- Resolver loja_id em lote ---
    lojas_existentes = pd.read_sql_query("SELECT id, codigo FROM lojas", conn)
    lojas_existentes["codigo"] = lojas_existentes["codigo"].astype(str).str.strip()

    df = df.merge(lojas_existentes, how="left", left_on="loja_codigo", right_on="codigo")

    # Criar novas lojas se não existirem
    novas_lojas = df[df["id"].isna()]["loja_codigo"].dropna().unique()
    for codigo in novas_lojas:
        conn.execute("INSERT OR IGNORE INTO lojas (codigo, nome) VALUES (?, ?)", (codigo, f"Loja {codigo}"))
    conn.commit()

    # Atualizar novamente com IDs corretos
    lojas_existentes = pd.read_sql_query("SELECT id, codigo FROM lojas", conn)
    lojas_existentes["codigo"] = lojas_existentes["codigo"].astype(str).str.strip()
    df = df.merge(lojas_existentes, how="left", left_on="loja_codigo", right_on="codigo", suffixes=("", "_loja"))

    # --- Preparar registros para inserção ---
    registros = df[[
        "data", "id_loja", "departamento_final", "secao_final",
        "codigo", "gtin", "quantidade", "custo_unitario",
        "valor", "descricao", "usuario"
    ]].values.tolist()

    # Limpar tabela antes de inserir
    conn.execute("DELETE FROM avarias")

    conn.executemany("""
        INSERT INTO avarias (
            data, loja_id, departamento, secao,
            codigo, gtin, quantidade, custo_unitario,
            valor, descricao, usuario
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, registros)

    conn.commit()
    conn.close()
    print(f"✅ {len(registros)} registros salvos no banco (processo otimizado).")

def verificar_totais_dataframe(df):
    totais = df.groupby("loja_codigo")["valor"].sum().reset_index()
    totais = totais.sort_values(by="loja_codigo", key=lambda x: x.astype(int))
    print("\n📊 Totais calculados direto do CSV:")
    for _, row in totais.iterrows():
        print(f"📊 Loja {row['loja_codigo']}: Total = {locale.currency(row['valor'] or 0, grouping=True)}")

def verificar_totais_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = """
        SELECT l.codigo, COUNT(a.id) AS registros, SUM(a.valor) AS total_avarias
        FROM avarias a
        JOIN lojas l ON a.loja_id = l.id
        GROUP BY l.codigo
        ORDER BY CAST(l.codigo AS INTEGER) ASC
    """
    resultados = cursor.execute(query).fetchall()
    conn.close()
    print("\n📊 Totais consultados direto do banco:")
    for codigo, registros, total in resultados:
        print(f"📊 Loja {codigo}: {registros} registros | Total = {locale.currency(total or 0, grouping=True)}")

if __name__ == "__main__":
    arquivos = localizar_avarias_csv()
    if arquivos:
        for arquivo in arquivos:
            tabela = montar_tabela_avarias(arquivo)
            if not tabela.empty:
                print(f"\n{arquivo.name} | Registros: {len(tabela)}")
                print(tabela.head(7))
                verificar_totais_dataframe(tabela)
                salvar_tabela_avarias(tabela)
                verificar_totais_banco()
            else:
                print(f"\n{arquivo.name} | ❌ Tabela não encontrada")
    else:
        print("⚠️ Nenhum arquivo relatorio_analitico_de_trocas.csv encontrado")
  