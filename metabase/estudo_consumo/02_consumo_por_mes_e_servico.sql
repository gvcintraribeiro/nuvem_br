-- =====================================================================
-- Metabase | Estudo de consumo | 2) Valor consumido por mês, por serviço
-- Engine: PostgreSQL 16 | Fonte: dw.fato_consumo_diario + dw.dim_data + dw.dim_produto
--
-- Distribui o consumo mensal entre os produtos (serviços). Traz também a
-- participação % do produto no total do mês; as participações somam 100% por mês.
--
-- Configuração no Metabase: Barra empilhada | X = competencia |
--   Série = produto | Y = valor_consumido
--   (participacao_pct serve para a versão "empilhada 100%" ou para tooltip)
-- =====================================================================
SELECT
    d.competencia,
    p.produto,
    -- SUM(f.valor_medido) AS valor_consumido,
    -- Soma por produto dividida pelo total do mês (janela por competência).
    ROUND(
        100 * SUM(f.valor_medido) / SUM(SUM(f.valor_medido)) OVER (PARTITION BY d.competencia),
        2
    ) AS participacao_pct
FROM dw.fato_consumo_diario f
JOIN dw.dim_data d ON d.sk_data = f.sk_data
JOIN dw.dim_produto p ON p.sk_produto = f.sk_produto
GROUP BY d.competencia, p.produto
ORDER BY d.competencia, participacao_pct
