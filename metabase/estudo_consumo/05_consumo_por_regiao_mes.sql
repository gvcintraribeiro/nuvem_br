-- =====================================================================
-- Metabase | Estudo de consumo | 5) Valor consumido por região, mês a mês
-- Engine: PostgreSQL 16 | Fonte: dw.fato_consumo_diario + dw.dim_data + dw.dim_regiao
--
-- Região = região de consumo da infraestrutura (dim_regiao, ex.: reg-sudeste,
-- reg-sul), que é um atributo do próprio consumo medido. Não é a região
-- geográfica do cliente usada em estudo_clientes.
-- Traz também a participação % da região no total do mês (as participações
-- somam 100% por mês).
--
-- Configuração no Metabase: Barra empilhada ou linha | X = competencia |
--   Série = regiao | Y = valor_consumido
-- =====================================================================
SELECT
    d.competencia,
    r.regiao,
    SUM(f.valor_medido) AS valor_consumido,
    -- Soma da região dividida pelo total do mês (janela por competência).
    ROUND(
        100 * SUM(f.valor_medido) / SUM(SUM(f.valor_medido)) OVER (PARTITION BY d.competencia),
        2
    ) AS participacao_pct
FROM dw.fato_consumo_diario f
JOIN dw.dim_data d ON d.sk_data = f.sk_data
JOIN dw.dim_regiao r ON r.sk_regiao = f.sk_regiao
GROUP BY d.competencia, r.regiao
ORDER BY d.competencia, r.regiao
