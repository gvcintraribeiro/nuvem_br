-- =====================================================================
-- Metabase | Estudo de receita | 1) Receita mês a mês (gráfico de linhas)
-- Engine: PostgreSQL 16 | Fonte: dw.fato_fatura + dw.dim_data
--
-- Receita = valor líquido (bruto - créditos), por competência de faturamento.
-- Faturas CANCELADAS ficam fora (a substituta já está entre as ativas).
--
-- Configuração no Metabase: Linha | X = competencia | Y = receita_liquida
-- =====================================================================
SELECT
    d.competencia,
    SUM(f.valor_liquido) AS receita_liquida
FROM dw.fato_fatura f
JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
WHERE f.status <> 'CANCELADA'
GROUP BY d.competencia
ORDER BY d.competencia
