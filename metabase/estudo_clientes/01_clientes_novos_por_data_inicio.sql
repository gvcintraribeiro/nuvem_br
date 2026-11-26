-- =====================================================================
-- Metabase | Estudo de clientes | 1) Clientes que entram na plataforma por mês
-- Engine: PostgreSQL 16 | Fonte: dw.dim_cliente
--
-- Data de início do cliente = início da primeira versão dele na dim_cliente
-- (MIN(valido_de)). Nos dados, o menor valido_de de cada cliente é igual ao
-- data_inicio do CRM, então a dimensão já carrega essa informação.
-- O membro "Não vinculado" (sk_cliente = -1) não é cliente e fica fora.
-- A série começa antes de jan/2026 (há clientes de 2025): é o histórico do CRM,
-- não só o período dos dados de consumo.
--
-- Configuração no Metabase: Barra | X = mes_inicio | Y = clientes_novos
--   (clientes_acumulados pode ser uma segunda série em linha)
-- =====================================================================
WITH inicio_cliente AS (
    -- 1 linha por cliente, com a data em que ele entrou.
    SELECT
        cliente_id,
        MIN(valido_de) AS data_inicio
    FROM dw.dim_cliente
    WHERE sk_cliente <> -1
    GROUP BY cliente_id
)
SELECT
    TO_CHAR(data_inicio, 'YYYY-MM') AS mes_inicio,
    COUNT(*) AS clientes_novos,
    -- Base total de clientes ao fim de cada mês de entrada.
    SUM(COUNT(*)) OVER (ORDER BY TO_CHAR(data_inicio, 'YYYY-MM')) AS clientes_acumulados
FROM inicio_cliente
GROUP BY TO_CHAR(data_inicio, 'YYYY-MM')
ORDER BY mes_inicio
