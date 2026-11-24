# %% [markdown]
# Leitura separada dos CSV da pasta data usando DuckDB.

# %%
from pathlib import Path

import duckdb


# %%
def ler_csv(conexao: duckdb.DuckDBPyConnection, caminho_csv: Path) -> duckdb.DuckDBPyRelation:
    return conexao.sql("SELECT * FROM read_csv_auto(?)", params=[str(caminho_csv)])


# %%
pasta_dados = Path("data")
conexao = duckdb.connect()
arquivos_csv = sorted(pasta_dados.glob("*.csv"))

dados_por_arquivo = {}

for caminho_csv in arquivos_csv:
    dados_por_arquivo[caminho_csv.stem] = ler_csv(conexao, caminho_csv)

# %%
crm_clientes_path = pasta_dados / "crm_clientes.csv"
crm_segmento_historico_path = pasta_dados / "crm_segmento_historico.csv"

clientes_com_segmento = conexao.sql(
    """
    SELECT
        c.*,
        s.*
    FROM read_csv_auto(?) c
    LEFT JOIN read_csv_auto(?) s
        ON c.cliente_id = s.cliente_id
    """,
    params=[str(crm_clientes_path), str(crm_segmento_historico_path)],
)

clientes_com_segmento.show()

# %%
cliente_ids_faltantes = conexao.sql(
    """
    SELECT DISTINCT s.cliente_id
    FROM read_csv_auto(?) s
    LEFT JOIN read_csv_auto(?) c
        ON s.cliente_id = c.cliente_id
    WHERE c.cliente_id IS NULL
    ORDER BY s.cliente_id
    """,
    params=[str(crm_segmento_historico_path), str(crm_clientes_path)],
)

cliente_ids_faltantes.show()

todos_ids_presentes = conexao.sql(
    """
    SELECT COUNT(*) = 0 AS todos_cliente_id_existem
    FROM (
        SELECT DISTINCT s.cliente_id
        FROM read_csv_auto(?) s
        LEFT JOIN read_csv_auto(?) c
            ON s.cliente_id = c.cliente_id
        WHERE c.cliente_id IS NULL
    ) faltantes
    """,
    params=[str(crm_segmento_historico_path), str(crm_clientes_path)],
)

todos_ids_presentes.show()

# %%
comparacao_inicio_cliente = conexao.sql(
    """
    WITH primeiro_valido_de AS (
        SELECT
            s.cliente_id,
            MIN(CAST(s.valido_de AS DATE)) AS valido_de_min
        FROM read_csv_auto(?) s
        GROUP BY s.cliente_id
    )
    SELECT
        p.cliente_id,
        p.valido_de_min,
        CAST(c.data_inicio AS DATE) AS data_inicio,
        p.valido_de_min = CAST(c.data_inicio AS DATE) AS datas_iguais
    FROM primeiro_valido_de p
    LEFT JOIN read_csv_auto(?) c
        ON p.cliente_id = c.cliente_id
    ORDER BY p.cliente_id
    """,
    params=[str(crm_segmento_historico_path), str(crm_clientes_path)],
)

comparacao_inicio_cliente.show()

validacao_inicio_cliente = conexao.sql(
    """
    WITH primeiro_valido_de AS (
        SELECT
            s.cliente_id,
            MIN(CAST(s.valido_de AS DATE)) AS valido_de_min
        FROM read_csv_auto(?) s
        GROUP BY s.cliente_id
    ),
    comparacao AS (
        SELECT
            p.cliente_id,
            p.valido_de_min,
            CAST(c.data_inicio AS DATE) AS data_inicio,
            p.valido_de_min = CAST(c.data_inicio AS DATE) AS datas_iguais
        FROM primeiro_valido_de p
        LEFT JOIN read_csv_auto(?) c
            ON p.cliente_id = c.cliente_id
    )
    SELECT
        COUNT(*) FILTER (WHERE datas_iguais IS NOT TRUE) = 0 AS valido_de_min_igual_data_inicio
    FROM comparacao
    """,
    params=[str(crm_segmento_historico_path), str(crm_clientes_path)],
)

validacao_inicio_cliente.show()

# %%
comparacao_segmento_recente = conexao.sql(
    """
    WITH historico_ordenado AS (
        SELECT
            s.cliente_id,
            s.segmento AS segmento_historico_recente,
            CAST(s.valido_de AS DATE) AS valido_de_recente
        FROM read_csv_auto(?) s
        QUALIFY ROW_NUMBER() OVER (
                PARTITION BY s.cliente_id
                ORDER BY CAST(s.valido_de AS DATE) DESC
            ) = 1
    )
    SELECT
        c.cliente_id,
        c.segmento AS segmento_cliente,
        h.segmento_historico_recente,
        h.valido_de_recente,
        c.segmento = h.segmento_historico_recente AS segmento_igual_ao_mais_recente
    FROM read_csv_auto(?) c
    LEFT JOIN historico_ordenado h
        ON c.cliente_id = h.cliente_id
    ORDER BY c.cliente_id
    """,
    params=[str(crm_segmento_historico_path), str(crm_clientes_path)],
)

comparacao_segmento_recente.show()

validacao_segmento_recente = conexao.sql(
    """
    WITH historico_ordenado AS (
        SELECT
            s.cliente_id,
            s.segmento AS segmento_historico_recente
        FROM read_csv_auto(?) s
        QUALIFY ROW_NUMBER() OVER (
                PARTITION BY s.cliente_id
                ORDER BY CAST(s.valido_de AS DATE) DESC
            ) = 1
    ),
    comparacao AS (
        SELECT
            c.cliente_id,
            c.segmento = h.segmento_historico_recente AS segmento_igual_ao_mais_recente
        FROM read_csv_auto(?) c
        LEFT JOIN historico_ordenado h
            ON c.cliente_id = h.cliente_id
    )
    SELECT
        COUNT(*) FILTER (WHERE segmento_igual_ao_mais_recente IS NOT TRUE) = 0
            AS todos_segmentos_iguais_ao_mais_recente
    FROM comparacao
    """,
    params=[str(crm_segmento_historico_path), str(crm_clientes_path)],
)

validacao_segmento_recente.show()

# %%
