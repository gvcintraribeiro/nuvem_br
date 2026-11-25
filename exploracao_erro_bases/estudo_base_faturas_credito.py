# %% [markdown]
# Análise da base de faturas e comparação com créditos.

# %%
from pathlib import Path

import duckdb


# %%
def ler_csv(
    conexao: duckdb.DuckDBPyConnection, caminho_csv: Path
) -> duckdb.DuckDBPyRelation:
    return conexao.sql("SELECT * FROM read_csv_auto(?)", params=[str(caminho_csv)])


# %%
pasta_dados = Path("data")
conexao = duckdb.connect()
arquivos_csv = sorted(pasta_dados.glob("*.csv"))

dados_por_arquivo = {}

for caminho_csv in arquivos_csv:
    dados_por_arquivo[caminho_csv.stem] = ler_csv(conexao, caminho_csv)

# %%
faturas_path = pasta_dados / "faturas.csv"
creditos_path = pasta_dados / "creditos.csv"

# Verifica se há fatura_id duplicado.
fatura_ids_duplicados = conexao.sql(
    """
    SELECT
        fatura_id,
        COUNT(*) AS quantidade
    FROM read_csv_auto(?)
    WHERE status != 'CANCELADA'
    GROUP BY fatura_id
    HAVING COUNT(*) > 1
    ORDER BY quantidade DESC, fatura_id
    """,
    params=[str(faturas_path)],
)

fatura_ids_duplicados.show()

existe_fatura_id_duplicado = conexao.sql(
    """
    SELECT COUNT(*) > 0 AS existe_fatura_id_duplicado
    FROM (
        SELECT fatura_id
        FROM read_csv_auto(?)
        WHERE status != 'CANCELADA'
        GROUP BY fatura_id
        HAVING COUNT(*) > 1
    ) duplicados
    """,
    params=[str(faturas_path)],
)

existe_fatura_id_duplicado.show()

# Verifica se a combinação conta_id e competencia está duplicada.
faturas_conta_competencia_duplicadas = conexao.sql(
    """
    SELECT
        conta_id,
        competencia,
        COUNT(*) AS quantidade
    FROM read_csv_auto(?)
    WHERE status != 'CANCELADA'
    GROUP BY conta_id, competencia
    HAVING COUNT(*) > 1
    ORDER BY quantidade DESC, conta_id, competencia
    """,
    params=[str(faturas_path)],
)

faturas_conta_competencia_duplicadas.show()

# %%
# Compara os créditos existentes em faturas e creditos por conta_id e competencia.
# Em creditos, os valores são somados caso existam vários registros para a mesma chave.
comparacao_creditos = conexao.sql(
    """
    WITH creditos_por_conta_competencia AS (
        SELECT
            conta_id,
            competencia,
            SUM(CAST(valor AS DECIMAL(18, 2))) AS valor_creditos_creditos
        FROM read_csv_auto(?)
        GROUP BY 1,2
        
    ),
    creditos_por_fatura AS (
        SELECT
            conta_id,
            competencia,
            SUM(CAST(valor_creditos AS DECIMAL(18, 2))) AS valor_creditos_faturas
        FROM read_csv_auto(?)
        WHERE CAST(valor_creditos AS DECIMAL(18, 2)) > 0
          AND status != 'CANCELADA'
        GROUP BY 1,2
        
    )
        SELECT 

        *,
        valor_creditos_creditos - valor_creditos_faturas

        FROM creditos_por_conta_competencia AS c

        LEFT JOIN creditos_por_fatura AS f
        ON c.conta_id = f.conta_id
        AND c.competencia = f.competencia 

        WHERE c.valor_creditos_creditos != f.valor_creditos_faturas
    """,
    params=[str(creditos_path), str(faturas_path)],
)

comparacao_creditos.show()


# %%
# Agrupa as faturas por status e traz os totais solicitados.
resumo_faturas_por_status = conexao.sql(
    """
    SELECT
        status,
        COUNT(DISTINCT fatura_id) AS quantidade_fatura_id,
        COUNT(DISTINCT conta_id) AS quantidade_conta_id,
        SUM(CAST(valor_bruto AS DECIMAL(18, 2))) AS soma_valor_bruto,
        SUM(CAST(valor_creditos AS DECIMAL(18, 2))) AS soma_valor_creditos,
        SUM(CAST(valor_liquido AS DECIMAL(18, 2))) AS soma_valor_liquido,
        COUNT(DISTINCT fatura_substituta_id) AS quantidade_fatura_substituta_id
    FROM read_csv_auto(?)
    GROUP BY status
    ORDER BY status
    """,
    params=[str(faturas_path)],
)

resumo_faturas_por_status.show()
