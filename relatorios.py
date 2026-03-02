import re
import pandas as pd
from pathlib import Path
import warnings
import unicodedata
import sqlite3
from datetime import datetime

warnings.simplefilter("ignore")

DB_PATH = "instance/expedicao_1.db"  # ajuste se necessário

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
    """Retorna a pasta Downloads do usuário."""
    return Path.home() / "Downloads"

def localizar_relatorios_padrao():
    """Localiza arquivos Relatorio.xlsx na pasta Downloads."""
    pasta_downloads = get_downloads_folder()
    padrao = re.compile(r"^Relatorio(\s*\(\d+\))?\.xlsx$", re.IGNORECASE)
    return [f for f in pasta_downloads.iterdir() if f.is_file() and padrao.match(f.name)]

def extrair_periodo(arquivo):
    """Extrai a data de período do relatório."""
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
    """Monta DataFrame com dados do relatório."""
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
                    df_correto.insert(0, "Data", normalizar_data(periodo))  # <-- normaliza aqui

                    # Conversão de colunas numéricas
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

def get_or_create_loja_id(cursor, codigo):
    """Retorna o id da loja pelo código, criando se não existir."""
    if not codigo:
        return None
    loja_row = cursor.execute("SELECT id FROM lojas WHERE codigo = ?", (codigo,)).fetchone()
    if loja_row:
        return loja_row[0]
    else:
        cursor.execute("INSERT INTO lojas (codigo, nome) VALUES (?, ?)", (codigo, f"Loja {codigo}"))
        return cursor.lastrowid

def salvar_tabela(df):
    """Salva DataFrame no banco SQLite na tabela vendas sem duplicar registros."""
    if df.empty:
        print("⚠️ Nenhum dado para salvar.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Garantir que a tabela vendas existe com loja_id
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        loja_id INTEGER NOT NULL,
        departamento TEXT NOT NULL,
        secao TEXT NOT NULL,
        codigo_interno INTEGER,
        gtin TEXT,
        produto TEXT,
        qtd_vendida REAL,
        venda REAL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE
    )
    """)

    # Índice único para evitar duplicatas
    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_unique
    ON vendas (data, loja_id, codigo_interno, gtin);
    """)

    registros_processados = 0

    for i, row in df.iterrows():
        # Ignora as duas últimas linhas (totais)
        if i >= len(df) - 2:
            continue

        loja_codigo = str(row.get("Loja")) if pd.notna(row.get("Loja")) else None

        # Ignora linhas sem loja ou com "total"
        if not loja_codigo or "total" in loja_codigo.lower():
            continue

        loja_id = get_or_create_loja_id(cursor, loja_codigo)

        valores = [
            normalizar_data(row.get("Data")),  # <-- normaliza aqui também
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

        cursor.execute("""
            INSERT OR REPLACE INTO vendas (
                data, loja_id, departamento, secao,
                codigo_interno, gtin, produto,
                qtd_vendida, venda
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, valores)
        registros_processados += 1

    conn.commit()
    conn.close()
    print(f"✅ {registros_processados} registros inseridos/atualizados no banco.")

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
