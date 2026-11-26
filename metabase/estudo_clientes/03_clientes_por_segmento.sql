-- =====================================================================
-- Metabase | Estudo de clientes | 3) Quantidade de clientes por segmento
-- Engine: PostgreSQL 16 | Fonte: dw.dim_cliente
--
-- Foto atual: usa a versão vigente de cada cliente (valido_ate = 9999-12-31),
-- ou seja, o segmento de hoje. A dim_cliente é SCD tipo 2 (1 linha por cliente
-- e período de segmento); filtrar a versão vigente evita contar o mesmo cliente
-- em dois segmentos. O membro "Não vinculado" (sk_cliente = -1) fica fora.
--
-- Configuração no Metabase: Pizza ou barra | Dimensão = segmento | Métrica = clientes
-- =====================================================================
SELECT
    segmento,
    COUNT(DISTINCT cliente_id) AS clientes
FROM dw.dim_cliente
WHERE valido_ate = DATE '9999-12-31'
  AND sk_cliente <> -1
GROUP BY segmento
ORDER BY clientes DESC
