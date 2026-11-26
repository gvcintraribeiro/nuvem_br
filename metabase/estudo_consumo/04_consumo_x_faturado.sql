-- =====================================================================
-- Metabase | Estudo de consumo | 5) Valor consumido x valor faturado
-- Engine: PostgreSQL 16 | Fonte: dw.fato_consumo_diario, dw.fato_fatura, dw.dim_data
--
-- Compara, por competência, o consumo medido com o valor bruto faturado
-- (antes dos créditos, que são desconto sobre o bruto). Faturas CANCELADAS
-- ficam fora (a substituta já está entre as ativas).
--   diferenca     = faturado - consumido (negativo = consumo não faturado)
--   pct_diferenca = diferença / consumido x 100
-- O consumo usa a data do dia; a fatura, a competência de faturamento.
-- FULL JOIN para não perder mês que existe só em um dos lados.
--
-- Configuração no Metabase: Barra agrupada ou linha | X = competencia |
--   Y = valor_consumido e valor_faturado
-- =====================================================================
WITH consumo AS (
    SELECT d.competencia, SUM(f.valor_medido) AS valor_consumido
    FROM dw.fato_consumo_diario f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data
    GROUP BY d.competencia
),
faturado AS (
    SELECT d.competencia, SUM(f.valor_bruto) AS valor_faturado
    FROM dw.fato_fatura f
    JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
    WHERE f.status <> 'CANCELADA'
    GROUP BY d.competencia
)
SELECT
    competencia,
    COALESCE(c.valor_consumido, 0) AS valor_consumido,
    COALESCE(f.valor_faturado, 0)  AS valor_faturado,
    COALESCE(f.valor_faturado, 0) - COALESCE(c.valor_consumido, 0) AS diferenca,
    ROUND(
        100 * (COALESCE(f.valor_faturado, 0) - COALESCE(c.valor_consumido, 0))
        / NULLIF(c.valor_consumido, 0),
        2
    ) AS pct_diferenca
FROM consumo c
FULL JOIN faturado f USING (competencia)
ORDER BY competencia
