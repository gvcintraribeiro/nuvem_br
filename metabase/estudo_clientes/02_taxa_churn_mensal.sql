-- =====================================================================
-- Metabase | Estudo de clientes | 2) Taxa de churn mês a mês
-- Engine: PostgreSQL 16 | Fonte: dw.fato_consumo_diario + dw.dim_data + dw.dim_cliente
--
-- Definição adotada (premissa):
--   * Cliente ativo no mês = teve consumo medido > 0 na competência (várias
--     contas do mesmo cliente contam uma vez; usa cliente_id, não sk_cliente).
--   * Perdido no mês M = ativo em M-1 e sem consumo em M.
--   * Churn % = clientes perdidos em M / clientes ativos em M-1 x 100.
-- O primeiro mês da série não tem mês anterior, então o churn dele é NULL.
-- Cliente que fica um mês sem consumo e volta depois conta como perdido naquele
-- mês (a base não tem data de cancelamento do contrato).
--
-- Configuração no Metabase: Linha | X = competencia | Y = churn_pct
-- =====================================================================
WITH cliente_mes AS (
    -- 1 linha por cliente e competência com consumo.
    SELECT DISTINCT
        d.competencia,
        c.cliente_id
    FROM dw.fato_consumo_diario f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    JOIN dw.dim_cliente c ON c.sk_cliente = f.sk_cliente
    WHERE f.valor_medido > 0
      AND c.sk_cliente <> -1
),
meses AS (
    -- Cada competência com o mês imediatamente anterior (AAAA-MM).
    SELECT
        competencia,
        TO_CHAR(TO_DATE(competencia || '-01', 'YYYY-MM-DD') - INTERVAL '1 month', 'YYYY-MM')
            AS competencia_anterior
    FROM (SELECT DISTINCT competencia FROM cliente_mes) x
)
SELECT
    m.competencia,
    COUNT(ant.cliente_id) AS clientes_mes_anterior,
    -- Estava ativo no mês anterior e não aparece neste mês.
    COUNT(ant.cliente_id) FILTER (WHERE atual.cliente_id IS NULL) AS clientes_perdidos,
    ROUND(
        100 * COUNT(ant.cliente_id) FILTER (WHERE atual.cliente_id IS NULL)
        / NULLIF(COUNT(ant.cliente_id), 0),
        2
    ) AS churn_pct
FROM meses m
LEFT JOIN cliente_mes ant
    ON ant.competencia = m.competencia_anterior
LEFT JOIN cliente_mes atual
    ON atual.competencia = m.competencia
   AND atual.cliente_id = ant.cliente_id
GROUP BY m.competencia
ORDER BY m.competencia
