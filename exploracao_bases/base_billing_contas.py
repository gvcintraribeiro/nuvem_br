# %% [markdown]
# Validação de dados faltantes na base billing_contas.

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
billing_contas_path = pasta_dados / "billing_contas.csv"

# Verifica dados faltantes na base billing_contas.
# Conta o número total de linhas e o número de valores faltantes para cada coluna relevante.
dados_faltantes_billing_contas = conexao.sql(
    """
    SELECT
        COUNT(*) AS total_linhas,
        COUNT(*) FILTER (
            WHERE cliente_id IS NULL
               OR TRIM(CAST(cliente_id AS VARCHAR)) = ''
        ) AS faltantes_cliente_id,
        COUNT(*) FILTER (
            WHERE cnpj_raiz IS NULL
               OR TRIM(CAST(cnpj_raiz AS VARCHAR)) = ''
        ) AS faltantes_cnpj_raiz
    FROM read_csv_auto(?)
    """,
    params=[str(billing_contas_path)],
)



dados_faltantes_billing_contas.show()

# %%
# Validação do tamanho do cnpj_raiz na base billing_contas.
cnpjs_raiz_com_tamanho_invalido = conexao.sql(
    """
    SELECT
        conta_id,
        cliente_id,
        cnpj_raiz,
        LENGTH(TRIM(CAST(cnpj_raiz AS VARCHAR))) AS quantidade_caracteres
    FROM read_csv_auto(?)
    WHERE cnpj_raiz IS NULL
       OR TRIM(CAST(cnpj_raiz AS VARCHAR)) = ''
       OR LENGTH(TRIM(CAST(cnpj_raiz AS VARCHAR))) != 8
    """,
    params=[str(billing_contas_path)],
)

cnpjs_raiz_com_tamanho_invalido.show()

validacao_cnpj_raiz = conexao.sql(
    """
    SELECT
        COUNT(*) = 0 AS todos_cnpj_raiz_com_8_caracteres,
        COUNT(*) AS quantidade_invalida
    FROM (
        SELECT cnpj_raiz
        FROM read_csv_auto(?)
        WHERE cnpj_raiz IS NULL
           OR TRIM(CAST(cnpj_raiz AS VARCHAR)) = ''
           OR LENGTH(TRIM(CAST(cnpj_raiz AS VARCHAR))) != 8
    ) invalidos
    """,
    params=[str(billing_contas_path)],
)

validacao_cnpj_raiz.show()

# %%
crm_clientes_path = pasta_dados / "crm_clientes.csv"

# Normaliza o CNPJ raiz e pega o cliente_id correspondente no CRM.
clientes_billing_com_cnpj = conexao.sql(
    """
    SELECT
        b.* EXCLUDE (cliente_id, cnpj_raiz),
        REGEXP_REPLACE(
            COALESCE(TRIM(CAST(b.cnpj_raiz AS VARCHAR)), ''),
            '[^0-9]',
            '',
            'g'
        ) AS cnpj_raiz,
        c.cliente_id AS cliente_id
    FROM read_csv_auto(?) b
    LEFT JOIN read_csv_auto(?) c
        ON REGEXP_REPLACE(
            COALESCE(TRIM(CAST(b.cnpj_raiz AS VARCHAR)), ''),
            '[^0-9]',
            '',
            'g'
        ) = REGEXP_REPLACE(
            COALESCE(TRIM(CAST(c.cnpj_raiz AS VARCHAR)), ''),
            '[^0-9]',
            '',
            'g'
        )
    """,
    params=[str(billing_contas_path), str(crm_clientes_path)],
)

clientes_billing_com_cnpj.show()

# %%
# Compara o cliente_id informado com o cliente_id correto recuperado pelo CNPJ.
comparacao_cliente_id = conexao.sql(
    """
    WITH billing_com_cnpj_normalizado AS (
        SELECT
            b.conta_id,
            NULLIF(TRIM(CAST(b.cliente_id AS VARCHAR)), '') AS cliente_id_informado,
            REGEXP_REPLACE(
                COALESCE(TRIM(CAST(b.cnpj_raiz AS VARCHAR)), ''),
                '[^0-9]',
                '',
                'g'
            ) AS cnpj_raiz_normalizado
        FROM read_csv_auto(?) b
    ),
    billing_com_cliente_crm AS (
        SELECT
            b.conta_id,
            b.cliente_id_informado,
            b.cnpj_raiz_normalizado,
            c.cliente_id AS cliente_id_crm
        FROM billing_com_cnpj_normalizado b
        LEFT JOIN read_csv_auto(?) c
            ON b.cnpj_raiz_normalizado = REGEXP_REPLACE(
                COALESCE(TRIM(CAST(c.cnpj_raiz AS VARCHAR)), ''),
                '[^0-9]',
                '',
                'g'
            )
    )

    SELECT 

    *

    FROM (

    SELECT
        conta_id,
        cliente_id_informado,
        cliente_id_crm,
        cnpj_raiz_normalizado,
        CASE
            WHEN cliente_id_informado IS NULL THEN 'cliente_id_nulo'
            WHEN cliente_id_informado = cliente_id_crm THEN 'cliente_id_correto'
            ELSE 'cliente_id_incorreto'
        END AS status_comparacao
    FROM billing_com_cliente_crm
    ) s

    WHERE status_comparacao != 'cliente_id_correto'
    """,
    params=[str(billing_contas_path), str(crm_clientes_path)],
)

comparacao_cliente_id.show()

resumo_comparacao_cliente_id = conexao.sql(
    """
    WITH billing_comparada AS (
        SELECT
            NULLIF(TRIM(CAST(b.cliente_id AS VARCHAR)), '') AS cliente_id_informado,
            c.cliente_id AS cliente_id_crm
        FROM read_csv_auto(?) b
        LEFT JOIN read_csv_auto(?) c
            ON REGEXP_REPLACE(
                COALESCE(TRIM(CAST(b.cnpj_raiz AS VARCHAR)), ''),
                '[^0-9]',
                '',
                'g'
            ) = REGEXP_REPLACE(
                COALESCE(TRIM(CAST(c.cnpj_raiz AS VARCHAR)), ''),
                '[^0-9]',
                '',
                'g'
            )
    )
    SELECT
        COUNT(*) FILTER (WHERE cliente_id_informado IS NULL) AS cliente_id_nulo,
        COUNT(*) FILTER (
            WHERE cliente_id_informado IS NOT NULL
              AND cliente_id_informado != cliente_id_crm
        ) AS cliente_id_incorreto
    FROM billing_comparada
    """,
    params=[str(billing_contas_path), str(crm_clientes_path)],
)

resumo_comparacao_cliente_id.show()

# %%
# Exporta a base cruzada para uma pasta ignorada pelo Git.
outputs_path = Path("outputs")
outputs_path.mkdir(exist_ok=True)

caminho_csv_saida = outputs_path / "clientes_billing_com_cnpj.csv"

conexao.sql(
    "COPY clientes_billing_com_cnpj TO ? (FORMAT CSV, HEADER)",
    params=[str(caminho_csv_saida)],
)

print(f"Arquivo salvo em: {caminho_csv_saida}")

# Conclusão: O arquivo com a base cruzada foi salvo na pasta "outputs".
# Existem CNPJ preenchidos que estavam em outtro formato, provavelmente eram dados com campo aberto e sem validação
# Existem 6 registros de cliente_id incorretos, que foram encontrados cruzando os cnpjs normalizados, porem não existia 
# nenhum preenchido e incorreto.