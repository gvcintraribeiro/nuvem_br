-- =====================================================================
-- Metabase | Estudo de clientes | 5) Receita paga por segmento
-- Engine: PostgreSQL 16 | Fonte: dw.fato_fatura + dw.dim_data + dw.dim_cliente
--
-- Receita paga = valor líquido (bruto - créditos) das faturas com status PAGA,
-- por competência de faturamento. Faturas CANCELADAS, ABERTAS e VENCIDAS ficam
-- fora (não é caixa recebido).
-- Segmento = o da versão do cliente válida na data de emissão da fatura (SCD2,
-- já resolvido em fato_fatura.sk_cliente), então um cliente que mudou de
-- segmento não reescreve o histórico. Faturas sem cliente vinculado aparecem
-- como "Não vinculado".
--
-- Configuração no Metabase: Barra empilhada | X = competencia |
--   Série = segmento | Y = receita_paga
-- =====================================================================
SELECT
    COALESCE(c.segmento, 'Não vinculado') AS segmento,
    SUM(f.valor_liquido) AS receita_paga
FROM dw.fato_fatura f
JOIN dw.dim_data d ON d.sk_data = f.sk_data_competencia
JOIN dw.dim_cliente c ON c.sk_cliente = f.sk_cliente
WHERE f.status = 'PAGA'
GROUP BY COALESCE(c.segmento, 'Não vinculado')
ORDER BY segmento
