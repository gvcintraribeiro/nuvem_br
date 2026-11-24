# %% [markdown]
# Validação de créditos SLA contra tickets de indisponibilidade.

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
creditos_path = pasta_dados / "creditos.csv"
tickets_path = pasta_dados / "tickets.csv"

# Lista os créditos SLA e verifica se existe pelo menos um ticket
# de Indisponibilidade para o mesmo conta_id.
creditos_sla_com_tickets = conexao.sql(
    """
    WITH creditos_sla AS (
        SELECT
            credito_id,
            conta_id,
            competencia,
            tipo,
            CAST(valor AS DECIMAL(18, 2)) AS valor,
            descricao
        FROM read_csv_auto(?)
        WHERE UPPER(TRIM(tipo)) = 'SLA'
    ),
    tickets_indisponibilidade AS (
        SELECT DISTINCT conta_id
        FROM read_csv_auto(?)
        WHERE UPPER(TRIM(categoria)) = 'INDISPONIBILIDADE'
    )
    SELECT
        c.credito_id,
        c.conta_id,
        c.competencia,
        c.tipo,
        c.valor,
        c.descricao,
        t.conta_id IS NOT NULL AS possui_ticket_indisponibilidade
    FROM creditos_sla c
    LEFT JOIN tickets_indisponibilidade t
        ON c.conta_id = t.conta_id
    ORDER BY c.conta_id, c.competencia, c.credito_id
    """,
    params=[str(creditos_path), str(tickets_path)],
)

creditos_sla_com_tickets.show()

# Créditos SLA sem ticket de Indisponibilidade associado ao conta_id.
creditos_sla_sem_ticket = conexao.sql(
    """
    WITH creditos_sla AS (
        SELECT
            credito_id,
            conta_id,
            competencia,
            tipo,
            CAST(valor AS DECIMAL(18, 2)) AS valor,
            descricao
        FROM read_csv_auto(?)
        WHERE UPPER(TRIM(tipo)) = 'SLA'
    ),
    tickets_indisponibilidade AS (
        SELECT DISTINCT conta_id
        FROM read_csv_auto(?)
        WHERE UPPER(TRIM(categoria)) = 'INDISPONIBILIDADE'
    )
    SELECT
        c.credito_id,
        c.conta_id,
        c.competencia,
        c.valor,
        c.descricao
    FROM creditos_sla c
    LEFT JOIN tickets_indisponibilidade t
        ON c.conta_id = t.conta_id
    WHERE t.conta_id IS NULL
    ORDER BY c.conta_id, c.competencia, c.credito_id
    """,
    params=[str(creditos_path), str(tickets_path)],
)

creditos_sla_sem_ticket.show()

# Resumo da validação.
resumo_creditos_sla = conexao.sql(
    """
    WITH creditos_sla AS (
        SELECT credito_id, conta_id
        FROM read_csv_auto(?)
        WHERE UPPER(TRIM(tipo)) = 'SLA'
    ),
    tickets_indisponibilidade AS (
        SELECT DISTINCT conta_id
        FROM read_csv_auto(?)
        WHERE UPPER(TRIM(categoria)) = 'INDISPONIBILIDADE'
    )
    SELECT
        COUNT(*) AS quantidade_creditos_sla,
        COUNT(*) FILTER (WHERE t.conta_id IS NOT NULL) AS creditos_com_ticket,
        COUNT(*) FILTER (WHERE t.conta_id IS NULL) AS creditos_sem_ticket,
        COUNT(*) FILTER (WHERE t.conta_id IS NULL) = 0 AS todos_creditos_sla_possuem_ticket
    FROM creditos_sla c
    LEFT JOIN tickets_indisponibilidade t
        ON c.conta_id = t.conta_id
    """,
    params=[str(creditos_path), str(tickets_path)],
)

resumo_creditos_sla.show()
