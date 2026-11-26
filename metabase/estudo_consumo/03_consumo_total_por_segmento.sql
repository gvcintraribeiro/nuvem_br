-- =====================================================================
-- Metabase | Estudo de consumo | 3) Valor consumido por segmento, mês a mês
-- Engine: PostgreSQL 16 | Fonte: dw.fato_consumo_diario + dw.dim_data + dw.dim_cliente
--
-- Consumo mensal de cada segmento, com a participação % do segmento no total do
-- mês (as participações somam 100% por mês). O segmento é o da versão do
-- cliente válida na data do consumo (SCD2, já resolvido em
-- fato_consumo_diario.sk_cliente): se o cliente mudou de segmento, o consumo
-- anterior continua no segmento antigo.
-- Consumo de contas sem cliente vinculado aparece como "Não vinculado".
--
-- Configuração no Metabase: Barra empilhada ou linha | X = competencia |
--   Série = segmento | Y = valor_consumido
-- =====================================================================
SELECT
    d.competencia,
    COALESCE(c.segmento, 'Não vinculado') AS segmento,
    SUM(f.valor_medido) AS valor_consumido,
    -- Soma do segmento dividida pelo total do mês (janela por competência).
    ROUND(
        100 * SUM(f.valor_medido) / SUM(SUM(f.valor_medido)) OVER (PARTITION BY d.competencia),
        2
    ) AS participacao_pct
FROM dw.fato_consumo_diario f
JOIN dw.dim_data d ON d.sk_data = f.sk_data
JOIN dw.dim_cliente c ON c.sk_cliente = f.sk_cliente
GROUP BY d.competencia, COALESCE(c.segmento, 'Não vinculado')
ORDER BY d.competencia, segmento
