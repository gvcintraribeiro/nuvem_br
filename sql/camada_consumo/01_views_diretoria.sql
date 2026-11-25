-- =====================================================================
-- NuvemBR - Camada de consumo (tarefa 2)
-- Engine: PostgreSQL 16 (schema mart, sobre o star schema do schema dw)
--
-- Convenções
--  * Receita faturada = faturas com status <> 'CANCELADA' (a substituta já está
--    entre as faturas ativas; contar a cancelada duplicaria a receita).
--  * Consumo medido = fato_consumo_diario.valor_medido, já sem lotes duplicados
--    e com TB-dia convertido para GB-dia (ver src/nuvem_br/transform.py).
--  * Competência (AAAA-MM) vem da dim_data. Consumo usa a data do dia; fatura usa
--    a competência de faturamento.
--  * Segmento do cliente é o da versão SCD2 válida na data do evento, então o
--    histórico não é reescrito quando o cliente muda de segmento.
--  * As views são recriadas a cada execução (CREATE OR REPLACE): script idempotente.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS mart;


-- ---------------------------------------------------------------------
-- 1) Visão única mensal: medido x faturado x créditos
-- Responde "estamos crescendo?" (crescimento mês a mês) e "onde perdemos
-- receita?" (consumo medido que não virou fatura e peso dos créditos).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.vw_receita_mensal AS
WITH consumo AS (
    SELECT d.competencia, SUM(f.valor_medido) AS consumo_medido
    FROM dw.fato_consumo_diario f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    GROUP BY d.competencia
),
faturado AS (
    SELECT
        d.competencia,
        SUM(f.valor_bruto)    AS faturado_bruto,
        SUM(f.valor_creditos) AS creditos,
        SUM(f.valor_liquido)  AS faturado_liquido
    FROM dw.fato_fatura f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
    WHERE f.status <> 'CANCELADA'
    GROUP BY d.competencia
),
mensal AS (
    SELECT
        competencia,
        COALESCE(c.consumo_medido, 0)   AS consumo_medido,
        COALESCE(f.faturado_bruto, 0)   AS faturado_bruto,
        COALESCE(f.creditos, 0)         AS creditos,
        COALESCE(f.faturado_liquido, 0) AS faturado_liquido
    FROM consumo c
    FULL JOIN faturado f USING (competencia)
)
SELECT
    competencia,
    consumo_medido,
    faturado_bruto,
    creditos,
    faturado_liquido,
    -- Receita medida que não chegou à fatura (positivo = perda).
    consumo_medido - faturado_bruto AS receita_nao_faturada,
    ROUND(100 * (consumo_medido - faturado_bruto) / NULLIF(consumo_medido, 0), 2)
        AS pct_nao_faturado,
    ROUND(100 * creditos / NULLIF(faturado_bruto, 0), 2) AS pct_creditos,
    -- Crescimento da receita líquida contra o mês anterior.
    ROUND(
        100 * (faturado_liquido - LAG(faturado_liquido) OVER (ORDER BY competencia))
        / NULLIF(LAG(faturado_liquido) OVER (ORDER BY competencia), 0),
        2
    ) AS crescimento_liquido_mom_pct
FROM mensal;


-- ---------------------------------------------------------------------
-- 2) Reconciliação por conta e mês (consumo medido x faturado)
-- Divergente = diferença acima de 0,5% do valor medido. Base do relatório de
-- anomalias: lista as contas e meses em que a fatura não bate com o medido.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.vw_reconciliacao_conta_mes AS
WITH medido AS (
    SELECT c.conta_id, d.competencia, SUM(f.valor_medido) AS valor_medido
    FROM dw.fato_consumo_diario f
    JOIN dw.dim_conta c ON c.sk_conta = f.sk_conta
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    GROUP BY c.conta_id, d.competencia
),
faturado AS (
    SELECT c.conta_id, d.competencia, SUM(f.valor_bruto) AS valor_faturado
    FROM dw.fato_fatura f
    JOIN dw.dim_conta c ON c.sk_conta = f.sk_conta
    JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
    WHERE f.status <> 'CANCELADA'
    GROUP BY c.conta_id, d.competencia
),
conciliado AS (
    -- FULL JOIN: não perde mês que existe só em uma das bases.
    SELECT
        COALESCE(m.conta_id, f.conta_id)       AS conta_id,
        COALESCE(m.competencia, f.competencia) AS competencia,
        COALESCE(m.valor_medido, 0)            AS valor_medido,
        COALESCE(f.valor_faturado, 0)          AS valor_faturado
    FROM medido m
    FULL JOIN faturado f
        ON f.conta_id = m.conta_id AND f.competencia = m.competencia
)
SELECT
    conta_id,
    competencia,
    valor_medido,
    valor_faturado,
    valor_faturado - valor_medido AS diferenca,
    ROUND(100 * (valor_faturado - valor_medido) / NULLIF(valor_medido, 0), 2)
        AS diferenca_pct,
    ABS(valor_faturado - valor_medido) > 0.005 * valor_medido AS divergente
FROM conciliado;


-- ---------------------------------------------------------------------
-- 3) Consumo por produto e mês
-- Mostra a composição da receita e o crescimento de cada produto.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.vw_consumo_produto_mensal AS
WITH produto_mes AS (
    SELECT d.competencia, p.produto, SUM(f.valor_medido) AS valor_medido
    FROM dw.fato_consumo_diario f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    JOIN dw.dim_produto p ON p.sk_produto = f.sk_produto
    GROUP BY d.competencia, p.produto
)
SELECT
    competencia,
    produto,
    valor_medido,
    ROUND(100 * valor_medido / SUM(valor_medido) OVER (PARTITION BY competencia), 2)
        AS participacao_pct,
    ROUND(
        100 * (valor_medido - LAG(valor_medido) OVER (PARTITION BY produto ORDER BY competencia))
        / NULLIF(LAG(valor_medido) OVER (PARTITION BY produto ORDER BY competencia), 0),
        2
    ) AS crescimento_mom_pct
FROM produto_mes;


-- ---------------------------------------------------------------------
-- 4) Faturamento por segmento e mês
-- O segmento é o da versão do cliente válida na data de emissão da fatura (SCD2).
-- Faturas do membro "Não vinculado" (sk_cliente = -1) aparecem como esse segmento.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.vw_faturado_segmento_mensal AS
SELECT
    d.competencia,
    c.segmento,
    COUNT(DISTINCT c.cliente_id) AS clientes_faturados,
    SUM(f.valor_bruto)           AS faturado_bruto,
    SUM(f.valor_creditos)        AS creditos,
    SUM(f.valor_liquido)         AS faturado_liquido
FROM dw.fato_fatura f
JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
JOIN dw.dim_cliente c ON c.sk_cliente = f.sk_cliente
WHERE f.status <> 'CANCELADA'
GROUP BY d.competencia, c.segmento;


-- ---------------------------------------------------------------------
-- 5) Créditos por mês e tipo
-- Separa o que é campanha (PROMOCIONAL), compensação (SLA) e desconto
-- negociado (COMERCIAL). Usa a tabela de créditos, não o campo da fatura.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.vw_creditos_mensal_tipo AS
SELECT
    d.competencia,
    k.tipo,
    COUNT(*)     AS quantidade,
    SUM(k.valor) AS valor
FROM dw.fato_credito k
JOIN dw.dim_data d ON d.sk_data = k.sk_data_competencia
GROUP BY d.competencia, k.tipo;


-- ---------------------------------------------------------------------
-- 6) Clientes ativos, novos e perdidos por mês
-- Ativo = cliente com consumo medido > 0 no mês (várias contas do mesmo cliente contam uma vez).
-- Novo = primeiro mês com consumo. Perdido = ativo no mês anterior e sem consumo
-- neste. Atenção: a série começa em jan/2026, então "novos" de jan inclui toda a
-- base existente; olhe os novos a partir de fev.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.vw_clientes_ativos_mensal AS
WITH cliente_mes AS (
    SELECT DISTINCT d.competencia, c.cliente_id
    FROM dw.fato_consumo_diario f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    JOIN dw.dim_cliente c ON c.sk_cliente = f.sk_cliente
    WHERE f.valor_medido > 0
),
primeira AS (
    SELECT cliente_id, MIN(competencia) AS primeira_competencia
    FROM cliente_mes
    GROUP BY cliente_id
),
perdidos AS (
    -- Clientes ativos no mês M que não aparecem no mês M+1 (contados em M+1).
    SELECT
        TO_CHAR(
            TO_DATE(a.competencia || '-01', 'YYYY-MM-DD') + INTERVAL '1 month', 'YYYY-MM'
        ) AS competencia,
        COUNT(*) AS clientes_perdidos
    FROM cliente_mes a
    LEFT JOIN cliente_mes b
        ON b.cliente_id = a.cliente_id
       AND b.competencia = TO_CHAR(
            TO_DATE(a.competencia || '-01', 'YYYY-MM-DD') + INTERVAL '1 month', 'YYYY-MM')
    WHERE b.cliente_id IS NULL
    GROUP BY 1
)
SELECT
    m.competencia,
    COUNT(*) AS clientes_ativos,
    COUNT(*) FILTER (WHERE p.primeira_competencia = m.competencia) AS clientes_novos,
    COALESCE(MAX(x.clientes_perdidos), 0) AS clientes_perdidos
FROM cliente_mes m
JOIN primeira p ON p.cliente_id = m.cliente_id
LEFT JOIN perdidos x ON x.competencia = m.competencia
GROUP BY m.competencia;
