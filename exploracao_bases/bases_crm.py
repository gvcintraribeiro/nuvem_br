# %% [markdown]
# Leitura separada dos CSV da pasta data usando DuckDB.

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
crm_clientes_path = pasta_dados / "crm_clientes.csv"
crm_segmento_historico_path = pasta_dados / "crm_segmento_historico.csv"

# Consulta clientes com segmento associado
# Esta consulta retorna todos os clientes com seus segmentos associados, se houver.
# Se um cliente não tiver segmento associado, os campos do segmento serão nulos.
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
# Consulta clientes que possuem IDs faltantes no CRM
# Esta consulta retorna os IDs de clientes que estão presentes no histórico de segmentos,
# mas não estão presentes na tabela de clientes.
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

# Consulta se todos os IDs de clientes do histórico de segmentos estão presentes na tabela de clientes
# Esta consulta retorna verdadeiro se todos os IDs de clientes do histórico de segmentos existirem na tabela de clientes, caso contrário, retorna falso.
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
# Comparação entre a data de início do cliente e a primeira data válida do segmento
# Esta consulta retorna, para cada cliente, a primeira data válida do segmento e a data de início do cliente, indicando se são iguais.
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

# Validação se a primeira data válida do segmento é igual à data de início do cliente
# Esta consulta retorna verdadeiro se todos os clientes tiverem a primeira data válida do segmento igual à data de início, caso contrário, retorna falso.
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
# Comparação entre o segmento mais recente do histórico e o segmento atual do cliente
# Esta consulta retorna, para cada cliente, o segmento atual e o segmento mais recente do histórico, indicando se são iguais.
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

# Validação se todos os clientes possuem o segmento mais recente igual ao segmento atual
# Esta consulta retorna verdadeiro se todos os clientes tiverem o segmento mais recente igual ao segmento atual, caso contrário, retorna falso.
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
# Verificação de CNPJs duplicados em crm_clientes
# Esta consulta lista os CNPJs que aparecem mais de uma vez.
cnpjs_duplicados = conexao.sql(
    """
    SELECT
        cnpj_raiz,
        COUNT(*) AS quantidade
    FROM read_csv_auto(?)
    GROUP BY cnpj_raiz
    HAVING COUNT(*) > 1
    ORDER BY quantidade DESC, cnpj_raiz
    """,
    params=[str(crm_clientes_path)],
)

cnpjs_duplicados.show()

# Esta consulta retorna verdadeiro quando existem CNPJs duplicados.
existe_cnpj_duplicado = conexao.sql(
    """
    SELECT COUNT(*) > 0 AS existe_cnpj_duplicado
    FROM (
        SELECT cnpj_raiz
        FROM read_csv_auto(?)
        GROUP BY cnpj_raiz
        HAVING COUNT(*) > 1
    ) duplicados
    """,
    params=[str(crm_clientes_path)],
)

existe_cnpj_duplicado.show()


# %%
# Verificação de razão social duplicada em crm_clientes
# Esta consulta lista as razões sociais que aparecem mais de uma vez.
razoes_sociais_duplicadas = conexao.sql(
    """
    SELECT
        razao_social,
        COUNT(*) AS quantidade
    FROM read_csv_auto(?)
    GROUP BY razao_social
    HAVING COUNT(*) > 1
    ORDER BY quantidade DESC, razao_social
    """,
    params=[str(crm_clientes_path)],
)

razoes_sociais_duplicadas.show()

# Esta consulta retorna verdadeiro quando existem razões sociais duplicadas.
existe_razao_social_duplicada = conexao.sql(
    """
    SELECT COUNT(*) > 0 AS existe_razao_social_duplicada
    FROM (
        SELECT razao_social
        FROM read_csv_auto(?)
        GROUP BY razao_social
        HAVING COUNT(*) > 1
    ) duplicadas
    """,
    params=[str(crm_clientes_path)],
)

existe_razao_social_duplicada.show()


# %%
## Conclusão
## A análise realizada mostra que:
## 1. Todos os IDs de clientes do histórico de segmentos estão presentes na tabela de clientes.
## 2. A primeira data válida do segmento é consistente com a data de início do cliente.
## 3. O segmento mais recente do histórico é consistente com o segmento atual do cliente.
## 4. Não existem CNPJs duplicados na tabela de clientes.
## 5. Existem razões sociais duplicadas na tabela de clientes, mas não prejudicam a integridade dos dados,
##    pois cada razão social pode corresponder a diferentes CNPJs.
