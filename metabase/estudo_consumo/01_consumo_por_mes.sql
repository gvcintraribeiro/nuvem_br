-- =====================================================================
-- Metabase | Estudo de consumo | 1) Valor consumido por mês
-- Engine: PostgreSQL 16 | Fonte: dw.fato_consumo_diario + dw.dim_data
--
-- Valor consumido = valor_medido (quantidade x preço unitário), já sem lotes
-- duplicados e com TB-dia convertido para GB-dia na carga. É o consumo medido,
-- antes de créditos: não é o valor faturado (ver consulta 5).
-- Agrupa pela data do consumo (competência do dia).
--
-- Configuração no Metabase: Linha ou barra | X = competencia | Y = valor_consumido
-- =====================================================================
SELECT
    d.competencia,
    SUM(f.valor_medido) AS valor_consumido
FROM dw.fato_consumo_diario f
JOIN dw.dim_data d ON d.sk_data = f.sk_data
GROUP BY d.competencia
ORDER BY d.competencia
