-- =====================================================================
-- Metabase | Estudo de receita | 3) Variação % do faturamento mês a mês (MoM)
-- Engine: PostgreSQL 16 | Fonte: dw.fato_fatura + dw.dim_data
--
-- MoM % = (receita do mês - receita do mês anterior) / receita do mês anterior.
-- Base: receita líquida (bruto - créditos). Faturas CANCELADAS ficam fora.
-- O primeiro mês não tem mês anterior, então o MoM dele é NULL.
--
-- Configuração no Metabase: Barra ou linha | X = competencia | Y = crescimento_mom_pct
-- =====================================================================
WITH mensal AS (
    SELECT
        d.competencia,
        SUM(f.valor_liquido) AS receita_liquida
    FROM dw.fato_fatura f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
    WHERE f.status <> 'CANCELADA'
    GROUP BY d.competencia
)
SELECT
    competencia,
    receita_liquida,
    LAG(receita_liquida) OVER (ORDER BY competencia) AS receita_mes_anterior,
    ROUND(
        100 * (receita_liquida - LAG(receita_liquida) OVER (ORDER BY competencia))
        / NULLIF(LAG(receita_liquida) OVER (ORDER BY competencia), 0),
        2
    ) AS crescimento_mom_pct
FROM mensal
ORDER BY competencia
