-- =====================================================================
-- Metabase | Estudo de receita | 2) % de créditos sobre o valor bruto, por mês
-- Engine: PostgreSQL 16 | Fonte: dw.fato_fatura + dw.dim_data
--
-- Quanto do faturamento bruto é abatido por créditos em cada competência:
--   % de créditos = soma(valor_creditos) / soma(valor_bruto) x 100
-- Faturas CANCELADAS ficam fora (a substituta já está entre as ativas).
--
-- Configuração no Metabase: Barra | X = competencia | Y = pct_creditos_sobre_bruto
-- =====================================================================
SELECT
    -- Competência de faturamento (AAAA-MM), vinda da dim_data.
    d.competencia,

    -- Soma antes de dividir: o % do mês é ponderado pelo valor das faturas,
    -- e não a média dos % de cada fatura. NULLIF evita divisão por zero.
    ROUND(100 * SUM(f.valor_creditos) / NULLIF(SUM(f.valor_bruto), 0), 2)
        AS pct_creditos_sobre_bruto

FROM dw.fato_fatura f
JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
-- Retira o valor cancelado do cálculo.
WHERE f.status <> 'CANCELADA'
GROUP BY d.competencia
ORDER BY d.competencia