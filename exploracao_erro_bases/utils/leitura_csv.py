from pathlib import Path

import duckdb


def ler_csv(
    conexao: duckdb.DuckDBPyConnection, caminho_csv: Path
) -> duckdb.DuckDBPyRelation:
    return conexao.sql("SELECT * FROM read_csv_auto(?)", params=[str(caminho_csv)])


def carregar_csvs(
    conexao: duckdb.DuckDBPyConnection, pasta_dados: Path
) -> dict[str, duckdb.DuckDBPyRelation]:
    """Lê todos os CSVs da pasta e devolve um dicionário {nome_do_arquivo: relação}."""
    return {
        caminho_csv.stem: ler_csv(conexao, caminho_csv)
        for caminho_csv in sorted(pasta_dados.glob("*.csv"))
    }
