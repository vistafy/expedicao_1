import pandas as pd
from pathlib import Path
from db import get_db

def atualizar_produtos_csv():
    caminho_csv = Path.home() / "Downloads" / "relatorio_estoque_geral.csv"

    # Lê o CSV com encoding latin1 (corrige acentos quebrados)
    df = pd.read_csv(caminho_csv, sep=";", encoding="latin1")
    df.columns = df.columns.str.strip()

    # Mapeia colunas com nomes quebrados para nomes corretos
    mapa_colunas = {
        "SeÃ§Ã£o": "Seção",
        "DescriÃ§Ã£o": "Descrição",
        "Ref. padrÃ£o": "Ref. padrão",
        "DisponÃ\xadvel": "Disponível",
        "ExposiÃ§Ã£o": "Exposição",
        "Venda MÃ©dia": "Venda Média",
        "PreÃ§o de venda": "Preço de venda",
        "Estq SeguranÃ§a": "Estq Segurança",
        "Estq MÃ¡ximo": "Estq Máximo"
    }
    df = df.rename(columns=mapa_colunas)

    # Seleciona colunas de interesse (garante que existam)
    colunas_interesse = ["Departamento", "Seção", "Descrição", "GTIN Principal", "Produto"]
    for col in colunas_interesse:
        if col not in df.columns:
            df[col] = ""  # cria coluna vazia se não existir

    dados = df[colunas_interesse].drop_duplicates().reset_index(drop=True)

    # Substitui NaN por string vazia para evitar erros
    dados = dados.fillna("")

    # Salva no banco
    conn = get_db()
    conn.execute("DELETE FROM produtos")  # limpa antes de repopular
    for _, row in dados.iterrows():
        conn.execute("""
            INSERT INTO produtos (departamento, secao, descricao, gtin, produto)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(row["Departamento"]).strip(),
            str(row["Seção"]).strip(),
            str(row["Descrição"]).strip(),
            str(row["GTIN Principal"]).strip(),
            str(row["Produto"]).strip()
        ))
    conn.commit()
    conn.close()
