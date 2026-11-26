-- =====================================================================
-- Metabase | Estudo de receita | 4) Taxa de inadimplência mês a mês
-- Engine: PostgreSQL 16 | Fonte: dw.fato_fatura + dw.dim_data
--
-- Definição adotada (premissa): inadimplência = valor líquido das faturas com
-- status VENCIDA / valor líquido total faturado na competência.
--   * Status possíveis: PAGA, ABERTA, VENCIDA (e CANCELADA, excluída aqui).
--   * ABERTA não conta como inadimplente: ainda está dentro do prazo.
--   * Base em valor líquido (o que o cliente realmente deve pagar).
-- A base não tem data de vencimento nem de pagamento; por isso a taxa usa o
-- status atual da fatura, e não o status na data de fechamento do mês.
--
-- Configuração no Metabase: Linha | X = competencia | Y = taxa_inadimplencia_pct
-- =====================================================================
SELECT
    d.competencia,
    SUM(f.valor_liquido) AS faturado_liquido,
    SUM(f.valor_liquido) FILTER (WHERE f.status = 'VENCIDA') AS valor_vencido,
    ROUND(
        100 * COALESCE(SUM(f.valor_liquido) FILTER (WHERE f.status = 'VENCIDA'), 0)
        / NULLIF(SUM(f.valor_liquido), 0),
        2
    ) AS taxa_inadimplencia_pct
FROM dw.fato_fatura f
JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
WHERE f.status <> 'CANCELADA'
GROUP BY d.competencia
ORDER BY d.competencia
