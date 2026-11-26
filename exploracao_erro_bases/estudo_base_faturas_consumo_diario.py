# %% [markdown]
# Conciliação consumo x faturas, investigação de contas divergentes,
# unidades por produto e lotes possivelmente duplicados.

# %%
import sys
from pathlib import Path

import duckdb

# Permite importar exploracao_erro_bases também ao rodar o arquivo direto (uv run arquivo.py).
sys.path.insert(0, str(Path.cwd()))
from exploracao_erro_bases.utils.leitura_csv import carregar_csvs

# %%
pasta_dados = Path("data")
conexao = duckdb.connect()
dados_por_arquivo = carregar_csvs(conexao, pasta_dados)

# %%
# Registra cada CSV já lido (dados_por_arquivo) como view, para não repetir
# read_csv_auto(?) em todas as consultas. Ex.: a view "faturas" aponta para faturas.csv.
for nome, relacao in dados_por_arquivo.items():
    relacao.create_view(nome, replace=True)

# %%
# View com o consumo TRATADO. Duas correções antes de comparar com a fatura:
# 1) Duplicidade de lote: a mesma chave (data, conta, produto, região) pode vir em
#    mais de um lote. Mantém só a carga mais recente (carregado_em).
# 2) Unidade: OBJECT_STORAGE chega em GB-dia e em TB-dia, mas o preço é por GB-dia.
#    Converte TB-dia para GB-dia (fator 1024, o que fez as faturas baterem).
conexao.sql("""
    CREATE OR REPLACE VIEW consumo_tratado AS
    SELECT
        conta_id,
        produto,
        regiao,
        CAST(data AS DATE) AS data,
        strftime(CAST(data AS DATE), '%Y-%m') AS competencia,
        quantidade * CASE WHEN unidade = 'TB-dia' THEN 1024 ELSE 1 END
            * preco_unitario AS valor
    FROM consumo_diario
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY data, conta_id, produto, regiao
        ORDER BY carregado_em DESC
    ) = 1
    """)

# %%
# Conciliação mensal por conta: valor medido (consumo) x valor faturado (bruto).
# - Faturas CANCELADAS ficam fora (a substituta já está nas faturas ativas).
# - FULL JOIN para não perder mês que existe só em uma das bases.
# - Divergente = diferença acima de 0,5% do valor medido.
conexao.sql("""
    CREATE OR REPLACE VIEW conciliacao_mensal AS
    WITH medido AS (
        SELECT conta_id, competencia, SUM(valor) AS valor_medido
        FROM consumo_tratado
        GROUP BY conta_id, competencia
    ),
    faturado AS (
        SELECT
            conta_id,
            CAST(competencia AS VARCHAR) AS competencia,
            SUM(valor_bruto) AS valor_faturado
        FROM faturas
        WHERE status <> 'CANCELADA'
        GROUP BY conta_id, CAST(competencia AS VARCHAR)
    )
    SELECT
        COALESCE(m.conta_id, f.conta_id) AS conta_id,
        COALESCE(m.competencia, f.competencia) AS competencia,
        COALESCE(m.valor_medido, 0) AS valor_medido,
        COALESCE(f.valor_faturado, 0) AS valor_faturado,
        COALESCE(f.valor_faturado, 0) - COALESCE(m.valor_medido, 0) AS diferenca
    FROM medido m
    FULL JOIN faturado f
        ON m.conta_id = f.conta_id AND m.competencia = f.competencia
    """)

# %%
# Consulta 1: contas com divergência em MAIS DE UM mês.
# Os valores medido, faturado e a diferença são somados só nos meses divergentes.
# Ordenado pela maior diferença absoluta (as mais divergentes primeiro).
contas_divergentes = conexao.sql("""
    SELECT
        conta_id,
        COUNT(*) AS meses_divergentes,
        MIN(competencia) AS primeiro_mes,
        MAX(competencia) AS ultimo_mes,
        ROUND(SUM(valor_medido), 2) AS valor_medido,
        ROUND(SUM(valor_faturado), 2) AS valor_faturado,
        ROUND(SUM(diferenca), 2) AS diferenca_total
    FROM conciliacao_mensal
    WHERE ABS(diferenca) > 0.005 * valor_medido
    GROUP BY conta_id
    HAVING COUNT(*) > 1
    ORDER BY ABS(SUM(diferenca)) DESC
    """)

contas_divergentes.show()

# %%
# Consulta 2: para as contas mais divergentes (top N da consulta 1),
# valor de consumo somado por produto.
# Para ver só um produto faltando na fatura, compare com a diferença da consulta 1.
TOP_N = 5
conexao.sql(
    "CREATE OR REPLACE VIEW contas_divergentes AS " + contas_divergentes.sql_query()
)

consumo_por_produto = conexao.sql(f"""
    SELECT
        t.conta_id,
        t.produto,
        ROUND(SUM(t.valor), 2) AS valor_medido
    FROM consumo_tratado t
    WHERE t.conta_id IN (SELECT conta_id FROM contas_divergentes LIMIT {TOP_N})
    GROUP BY t.conta_id, t.produto
    ORDER BY t.conta_id, valor_medido DESC
    """)

consumo_por_produto.show()

# %%
# Consulta 3: para cada produto e unidade, primeira e última data em que aparece.
# Usa a tabela bruta (consumo_diario), pois aqui o objetivo é ver a unidade como veio.
unidades_por_produto = conexao.sql("""
    SELECT
        produto,
        unidade,
        MIN(CAST(data AS DATE)) AS primeira_data,
        MAX(CAST(data AS DATE)) AS ultima_data,
        COUNT(*) AS linhas
    FROM consumo_diario
    GROUP BY produto, unidade
    ORDER BY produto, primeira_data
    """)

unidades_por_produto.show()

# %%
# Consulta 4: lotes possivelmente duplicados.
# O lote_id tem o formato L<data>-<sequência> (ex.: L20260514-02): o separador é "-".
# Lote base = parte antes do "-". Candidatos = lote base que aparece com
# mais de uma sequência diferente depois do "-".
lotes_possiveis_duplicados = conexao.sql("""
    WITH lotes AS (
        SELECT
            lote_id,
            split_part(lote_id, '-', 1) AS lote_base,
            split_part(lote_id, '-', 2) AS sequencia,
            COUNT(*) AS linhas,
            MIN(carregado_em) AS primeira_carga,
            MAX(carregado_em) AS ultima_carga
        FROM consumo_diario
        GROUP BY lote_id
    )
    SELECT
        lote_base,
        lote_id,
        sequencia,
        linhas,
        primeira_carga,
        ultima_carga,
        COUNT(*) OVER (PARTITION BY lote_base) AS lotes_na_base
    FROM lotes
    QUALIFY COUNT(DISTINCT sequencia) OVER (PARTITION BY lote_base) > 1
    ORDER BY lote_base, sequencia
    """)

lotes_possiveis_duplicados.show()
