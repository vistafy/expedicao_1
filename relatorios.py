import re
import pandas as pd
from pathlib import Path
import warnings
import unicodedata
import psycopg2
from datetime import datetime

warnings.simplefilter("ignore")

# 🔧 Configuração da conexão PostgreSQL
PG_CONN = {
    "dbname": "expedicao_1",
    "user": "postgres",
    "password": "rc04202894",  # troque pela sua senha real
    "host": "localhost",
    "port": "5432"
}

def normalizar(texto):
    """Normaliza texto para minúsculo e sem acentos."""
    if not isinstance(texto, str):
        return ""
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    return texto

def normalizar_data(data_str):
    """Converte datas para formato YYYY-MM-DD"""
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        return data_str

def get_downloads_folder():
    return Path.home() / "Downloads"

def localizar_relatorios_padrao():
    pasta_downloads = get_downloads_folder()
    padrao = re.compile(r"^Relatorio(\s*\(\d+\))?\.xlsx$", re.IGNORECASE)
    return [f for f in pasta_downloads.iterdir() if f.is_file() and padrao.match(f.name)]

def extrair_periodo(arquivo):
    try:
        xls = pd.ExcelFile(arquivo)
        for sheet in xls.sheet_names:
            df = pd.read_excel(arquivo, sheet_name=sheet, header=None)
            for linha in df.values:
                for celula in linha:
                    if isinstance(celula, str) and "período" in celula.lower():
                        match = re.search(r"(\d{2}/\d{2}/\d{4})", celula)
                        if match:
                            return match.group(1)
                        return celula.strip()
    except Exception as e:
        print(f"❌ Erro ao extrair período: {e}")
    return None

def montar_tabela(arquivo, periodo):
    esperado = ["loja","departamento","seção","código interno","gtin","produto","qtd vendida","venda(r$)"]
    try:
        xls = pd.ExcelFile(arquivo)
        for sheet in xls.sheet_names:
            df = pd.read_excel(arquivo, sheet_name=sheet, header=None)
            for i, linha in enumerate(df.values):
                colunas = [normalizar(str(c)) for c in linha if isinstance(c, str)]
                encontrados = sum(1 for e in esperado if any(e in c for c in colunas))
                if encontrados >= len(esperado) // 2:
                    df_correto = pd.read_excel(arquivo, sheet_name=sheet, header=i)
                    df_correto.insert(0, "Data", normalizar_data(periodo))

                    for col in ["Código Interno"]:
                        if col in df_correto.columns:
                            df_correto[col] = pd.to_numeric(df_correto[col], errors="coerce").astype("Int64")

                    for col in ["Qtd Vendida", "Venda(R$)"]:
                        if col in df_correto.columns:
                            df_correto[col] = pd.to_numeric(df_correto[col], errors="coerce")

                    return df_correto
    except Exception as e:
        print(f"❌ Erro ao montar tabela: {e}")
    return pd.DataFrame()

def get_or_create_loja_id(cur, codigo):
    if not codigo:
        return None
    cur.execute("SELECT id FROM lojas WHERE codigo = %s", (codigo,))
    loja_row = cur.fetchone()
    if loja_row:
        return loja_row[0]
    else:
        cur.execute("INSERT INTO lojas (codigo, nome) VALUES (%s, %s) RETURNING id", (codigo, f"Loja {codigo}"))
        return cur.fetchone()[0]

def salvar_tabela(df):
    if df.empty:
        print("⚠️ Nenhum dado para salvar.")
        return

    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()

    registros_processados = 0

    for i, row in df.iterrows():
        if i >= len(df) - 2:
            continue

        loja_codigo = str(row.get("Loja")) if pd.notna(row.get("Loja")) else None
        if not loja_codigo or "total" in loja_codigo.lower():
            continue

        loja_id = get_or_create_loja_id(cur, loja_codigo)

        valores = [
            normalizar_data(row.get("Data")),
            loja_id,
            str(row.get("Departamento")) if pd.notna(row.get("Departamento")) else "DESCONHECIDO",
            str(row.get("Seção")) if pd.notna(row.get("Seção")) else "DESCONHECIDO",
            row.get("Código Interno"),
            str(row.get("GTIN")) if pd.notna(row.get("GTIN")) else None,
            row.get("Produto"),
            row.get("Qtd Vendida"),
            row.get("Venda(R$)")
        ]
        valores = [None if pd.isna(v) else v for v in valores]

        cur.execute("""
            INSERT INTO vendas (
                data, loja_id, departamento, secao,
                codigo_interno, gtin, produto,
                qtd_vendida, venda
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (data, loja_id, codigo_interno, gtin) DO UPDATE
            SET departamento = EXCLUDED.departamento,
                secao = EXCLUDED.secao,
                produto = EXCLUDED.produto,
                qtd_vendida = EXCLUDED.qtd_vendida,
                venda = EXCLUDED.venda
        """, valores)
        registros_processados += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ {registros_processados} registros inseridos/atualizados no banco PostgreSQL.")

if __name__ == "__main__":
    relatorios = localizar_relatorios_padrao()
    if relatorios:
        for arquivo in relatorios:
            periodo = extrair_periodo(arquivo)
            tabela = montar_tabela(arquivo, periodo)
            if not tabela.empty:
                print(f"\n{arquivo.name} | Data: {periodo}")
                print(tabela.head(5))
                salvar_tabela(tabela)
            else:
                print(f"\n{arquivo.name} | Data: {periodo} | ❌ Tabela não encontrada")
    else:
        print("Nenhum arquivo Relatorio.xlsx encontrado na pasta Downloads.")
