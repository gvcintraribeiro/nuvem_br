"""Leitura dos CSVs e tratamentos com DuckDB.

Devolve, para cada tabela do schema dw, uma lista de dicionários com as mesmas
colunas dos modelos de models.py. Nada é gravado aqui.

Regras de tratamento aplicadas (e onde):
 1. Duplicata de lote: mantém só a linha de maior carregado_em (fato_consumo_diario).
 2. Unidade mista: OBJECT_STORAGE em TB-dia vira GB-dia (x1024) (fato_consumo_diario).
 3. Faturas canceladas: são carregadas; quem calcula receita filtra status <> 'CANCELADA'.
 4. valor_liquido invertido: recalculado como bruto - créditos; o original fica em
    valor_liquido_origem (fato_fatura).
 5. Conta sem cliente_id: recuperado pelo CNPJ raiz normalizado. Se mesmo assim não
    houver cliente, aponta para sk_cliente = -1.
 6. sk_cliente dos fatos = versão da dim_cliente (SCD2) válida na data do evento
    (data do consumo, data de emissão da fatura e último dia da competência do crédito).
Extra: CNPJ raiz normalizado para 8 dígitos (remove máscara) em todas as bases.
"""

import logging
from datetime import date
from pathlib import Path

import duckdb

from nuvem_br.models import FIM_VIGENCIA, SK_CLIENTE_NAO_VINCULADO

logger = logging.getLogger(__name__)

# Converte uma expressão de data em sk_data (AAAAMMDD).
SK_DATA = "CAST(strftime({expr}, '%Y%m%d') AS INTEGER)"


def ler_csv(
    conexao: duckdb.DuckDBPyConnection, caminho_csv: Path
) -> duckdb.DuckDBPyRelation:
    return conexao.sql("SELECT * FROM read_csv_auto(?)", params=[str(caminho_csv)])


def _sk_data(expr: str) -> str:
    return SK_DATA.format(expr=expr)


def _linhas(relacao: duckdb.DuckDBPyRelation) -> list[dict]:
    """Converte o resultado de uma consulta em lista de dicionários (sem pandas)."""
    colunas = relacao.columns
    return [dict(zip(colunas, linha)) for linha in relacao.fetchall()]


def _escalar(conexao: duckdb.DuckDBPyConnection, sql: str):
    """Executa uma consulta de uma linha e uma coluna."""
    return conexao.sql(sql).fetchall()[0][0]


# --------------------------------------------------------------------------
# Views de apoio e dimensões
# --------------------------------------------------------------------------
def _criar_views_dimensoes(conexao: duckdb.DuckDBPyConnection) -> None:
    """Cria no DuckDB as views das dimensões (usadas nos joins dos fatos)."""

    # Calendário: do 1º de janeiro do ano da menor data até 31/12 do ano da maior
    # data encontrada em qualquer base (inclui vigências de segmento e emissões).
    conexao.sql(f"""
        CREATE OR REPLACE VIEW dim_data AS
        WITH datas AS (
            SELECT valido_de AS d FROM crm_segmento_historico
            UNION ALL SELECT data_criacao FROM billing_contas
            UNION ALL SELECT CAST(data AS DATE) FROM consumo_diario
            UNION ALL SELECT data_emissao FROM faturas
            UNION ALL SELECT CAST(competencia || '-01' AS DATE) FROM faturas
            UNION ALL SELECT CAST(competencia || '-01' AS DATE) FROM creditos
            UNION ALL SELECT CAST(aberto_em AS DATE) FROM tickets
        ),
        limites AS (SELECT MIN(d) AS minimo, MAX(d) AS maximo FROM datas)
        SELECT
            {_sk_data('CAST(g.d AS DATE)')} AS sk_data,
            CAST(g.d AS DATE) AS data,
            strftime(g.d, '%Y-%m') AS competencia,
            MONTH(g.d) AS numero_mes,
            LIST_EXTRACT(
                ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'],
                MONTH(g.d)
            ) AS nome_mes,
            QUARTER(g.d) AS trimestre,
            LIST_EXTRACT(
                ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira',
                 'Sexta-feira', 'Sábado', 'Domingo'],
                ISODOW(g.d)
            ) AS dia_semana,
            ISODOW(g.d) AS numero_dia_semana,  -- ISO: 1 = segunda ... 7 = domingo
            DAYOFYEAR(g.d) AS dia_ano
        FROM limites,
             generate_series(
                 DATE_TRUNC('year', minimo),
                 DATE_TRUNC('year', maximo) + INTERVAL 1 YEAR - INTERVAL 1 DAY,
                 INTERVAL 1 DAY
             ) AS g(d)
        """)

    # CNPJ raiz só com dígitos (remove máscara) nas duas pontas do vínculo.
    conexao.sql("""
        CREATE OR REPLACE VIEW conta_normalizada AS
        SELECT
            conta_id,
            NULLIF(TRIM(cliente_id), '') AS cliente_id_informado,
            TRIM(CAST(cnpj_raiz AS VARCHAR)) AS cnpj_raiz_original,
            REGEXP_REPLACE(TRIM(CAST(cnpj_raiz AS VARCHAR)), '[^0-9]', '', 'g') AS cnpj_raiz,
            data_criacao
        FROM billing_contas
        """)

    # Regra 5: o vínculo manual manda; se estiver vazio, recupera pelo CNPJ raiz
    # (no CRM o CNPJ raiz é único).
    conexao.sql("""
        CREATE OR REPLACE VIEW conta_cliente AS
        SELECT
            n.*,
            COALESCE(n.cliente_id_informado, c.cliente_id) AS cliente_id
        FROM conta_normalizada n
        LEFT JOIN (
            SELECT
                cliente_id,
                REGEXP_REPLACE(CAST(cnpj_raiz AS VARCHAR), '[^0-9]', '', 'g') AS cnpj_raiz
            FROM crm_clientes
        ) c
            ON c.cnpj_raiz = n.cnpj_raiz
        """)

    conexao.sql("""
        CREATE OR REPLACE VIEW dim_conta AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY conta_id) AS sk_conta,
            conta_id,
            cnpj_raiz,
            data_criacao
        FROM conta_normalizada
        """)

    # SCD tipo 2: 1 linha por cliente e vigência do segmento (valido_ate é inclusivo e
    # a versão seguinte começa no dia seguinte). canal e uf são tipo 1, vêm do CRM.
    # valido_ate nulo (vigente) vira 9999-12-31 para permitir o join por período.
    conexao.sql(f"""
        CREATE OR REPLACE VIEW dim_cliente AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY h.cliente_id, h.valido_de) AS sk_cliente,
            h.cliente_id,
            h.segmento,
            c.canal,
            c.uf,
            h.valido_de,
            COALESCE(h.valido_ate, DATE '{FIM_VIGENCIA.isoformat()}') AS valido_ate
        FROM crm_segmento_historico h
        JOIN crm_clientes c ON c.cliente_id = h.cliente_id
        """)

    # Conta x versão do cliente: permite achar o sk_cliente válido na data do evento
    # com um único LEFT JOIN nos fatos. Sem linha = sem cliente vigente (vira -1).
    conexao.sql("""
        CREATE OR REPLACE VIEW conta_cliente_versao AS
        SELECT cc.conta_id, d.sk_cliente, d.valido_de, d.valido_ate
        FROM conta_cliente cc
        JOIN dim_cliente d ON d.cliente_id = cc.cliente_id
        """)

    # OBJECT_STORAGE chega também em TB-dia, mas a unidade-base de cobrança é GB-dia.
    conexao.sql("""
        CREATE OR REPLACE VIEW dim_produto AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY produto) AS sk_produto,
            produto,
            unidade_base
        FROM (
            SELECT DISTINCT
                produto,
                CASE WHEN unidade = 'TB-dia' THEN 'GB-dia' ELSE unidade END AS unidade_base
            FROM consumo_diario
        )
        """)

    conexao.sql("""
        CREATE OR REPLACE VIEW dim_regiao AS
        SELECT ROW_NUMBER() OVER (ORDER BY regiao) AS sk_regiao, regiao
        FROM (SELECT DISTINCT regiao FROM consumo_diario)
        """)


# --------------------------------------------------------------------------
# Fatos
# --------------------------------------------------------------------------
def _fato_consumo_diario(conexao: duckdb.DuckDBPyConnection) -> list[dict]:
    """Grão: dia x conta x produto x região."""
    return _linhas(conexao.sql(f"""
            WITH deduplicado AS (
                -- Regra 1: a mesma chave pode vir em mais de um lote; fica a carga
                -- mais recente (lote_id desempata cargas no mesmo instante).
                SELECT *
                FROM consumo_diario
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY data, conta_id, produto, regiao
                    ORDER BY carregado_em DESC, lote_id DESC
                ) = 1
            ),
            convertido AS (
                -- Regra 2: TB-dia -> GB-dia (x1024), pois o preço é por GB-dia.
                SELECT
                    *,
                    CAST(quantidade AS DECIMAL(18, 4))
                        * CASE WHEN unidade = 'TB-dia' THEN 1024 ELSE 1 END AS qtd_base
                FROM deduplicado
            )
            SELECT
                {_sk_data('x.data')} AS sk_data,
                c.sk_conta,
                p.sk_produto,
                r.sk_regiao,
                -- Regra 6: versão do cliente válida na data do consumo.
                COALESCE(v.sk_cliente, {SK_CLIENTE_NAO_VINCULADO}) AS sk_cliente,
                CAST(x.qtd_base AS DECIMAL(18, 4)) AS quantidade_base,
                CAST(ROUND(x.qtd_base * CAST(x.preco_unitario AS DECIMAL(12, 6)), 4)
                     AS DECIMAL(18, 4)) AS valor_medido,
                x.lote_id
            FROM convertido x
            JOIN dim_conta c ON c.conta_id = x.conta_id
            JOIN dim_produto p ON p.produto = x.produto
            JOIN dim_regiao r ON r.regiao = x.regiao
            LEFT JOIN conta_cliente_versao v
                ON v.conta_id = x.conta_id
               AND x.data BETWEEN v.valido_de AND v.valido_ate
            """))


def _fato_fatura(conexao: duckdb.DuckDBPyConnection) -> list[dict]:
    """Grão: 1 fatura emitida (todas, inclusive canceladas e substitutas)."""
    return _linhas(conexao.sql(f"""
            SELECT
                f.fatura_id,
                {_sk_data('f.data_emissao')} AS sk_data_emissao,
                {_sk_data("CAST(f.competencia || '-01' AS DATE)")} AS sk_data_competencia,
                c.sk_conta,
                -- Regra 6: versão do cliente válida na data de emissão.
                COALESCE(v.sk_cliente, {SK_CLIENTE_NAO_VINCULADO}) AS sk_cliente,
                CAST(f.valor_bruto AS DECIMAL(18, 4)) AS valor_bruto,
                CAST(f.valor_creditos AS DECIMAL(18, 4)) AS valor_creditos,
                -- Regra 4: recalcula o líquido (em ago/2026 veio como bruto + créditos).
                CAST(f.valor_bruto AS DECIMAL(18, 4))
                    - CAST(f.valor_creditos AS DECIMAL(18, 4)) AS valor_liquido,
                CAST(f.valor_liquido AS DECIMAL(18, 4)) AS valor_liquido_origem,
                f.status,
                f.fatura_substituta_id
            FROM faturas f
            JOIN dim_conta c ON c.conta_id = f.conta_id
            LEFT JOIN conta_cliente_versao v
                ON v.conta_id = f.conta_id
               AND f.data_emissao BETWEEN v.valido_de AND v.valido_ate
            """))


def _fato_credito(conexao: duckdb.DuckDBPyConnection) -> list[dict]:
    """Grão: 1 crédito concedido."""
    return _linhas(conexao.sql(f"""
            SELECT
                k.credito_id,
                {_sk_data("CAST(k.competencia || '-01' AS DATE)")} AS sk_data_competencia,
                c.sk_conta,
                -- Regra 6: versão do cliente válida no ÚLTIMO dia da competência. No 1º dia,
                -- os créditos PROMOCIONAIS de clientes novos (início no meio do mês) ficariam
                -- sem cliente vigente (28 créditos, ~R$ 22,6 mil).
                COALESCE(v.sk_cliente, {SK_CLIENTE_NAO_VINCULADO}) AS sk_cliente,
                k.tipo,
                CAST(k.valor AS DECIMAL(18, 4)) AS valor
            FROM creditos k
            JOIN dim_conta c ON c.conta_id = k.conta_id
            LEFT JOIN conta_cliente_versao v
                ON v.conta_id = k.conta_id
               AND LAST_DAY(CAST(k.competencia || '-01' AS DATE)) BETWEEN v.valido_de AND v.valido_ate
            """))


def _fato_ticket(conexao: duckdb.DuckDBPyConnection) -> list[dict]:
    """Grão: 1 chamado. aberto_em vem em UTC (sufixo Z) e resolvido_em sem fuso:
    assume-se UTC nos dois (a sessão do DuckDB está em UTC)."""
    return _linhas(conexao.sql(f"""
            SELECT
                t.ticket_id,
                {_sk_data('CAST(t.aberto_em AS DATE)')} AS sk_data_abertura,
                c.sk_conta,
                t.severidade,
                t.categoria,
                CAST(ROUND(
                    EXTRACT(EPOCH FROM (t.resolvido_em - CAST(t.aberto_em AS TIMESTAMP))) / 3600,
                    4
                ) AS DECIMAL(18, 4)) AS horas_resolucao
            FROM tickets t
            JOIN dim_conta c ON c.conta_id = t.conta_id
            """))


# --------------------------------------------------------------------------
# Registro de anomalias (log)
# --------------------------------------------------------------------------
def _registrar_anomalias(
    conexao: duckdb.DuckDBPyConnection, tabelas: dict[str, list[dict]]
) -> None:
    """Escreve no log o que foi tratado, com a quantidade de registros afetados."""
    bruto = _escalar(conexao, "SELECT COUNT(*) FROM consumo_diario")
    duplicadas = bruto - len(tabelas["fato_consumo_diario"])
    logger.warning(
        "Regra 1: %d linhas de consumo duplicadas por lote removidas.", duplicadas
    )

    em_tb = _escalar(
        conexao, "SELECT COUNT(*) FROM consumo_diario WHERE unidade = 'TB-dia'"
    )
    logger.warning(
        "Regra 2: %d linhas brutas em TB-dia convertidas para GB-dia.", em_tb
    )

    canceladas = sum(1 for f in tabelas["fato_fatura"] if f["status"] == "CANCELADA")
    logger.info(
        "Regra 3: %d faturas CANCELADA carregadas (filtrar na receita).", canceladas
    )

    divergentes = [
        f
        for f in tabelas["fato_fatura"]
        if f["valor_liquido"] != f["valor_liquido_origem"]
    ]
    invertidas = [
        f
        for f in divergentes
        if f["valor_liquido_origem"] == f["valor_bruto"] + f["valor_creditos"]
    ]
    excesso = sum(f["valor_liquido_origem"] - f["valor_liquido"] for f in divergentes)
    logger.warning(
        "Regra 4: %d faturas com valor_liquido diferente de bruto - créditos "
        "(%d são bruto + créditos); líquido de origem excedia em R$ %s.",
        len(divergentes),
        len(invertidas),
        excesso,
    )
    if len(divergentes) != len(invertidas):
        logger.error(
            "ANOMALIA NOVA: %d faturas com líquido divergente que não é bruto + créditos.",
            len(divergentes) - len(invertidas),
        )

    recuperadas = _escalar(
        conexao,
        "SELECT COUNT(*) FROM conta_cliente WHERE cliente_id_informado IS NULL AND cliente_id IS NOT NULL",
    )
    sem_cliente = _escalar(
        conexao, "SELECT COUNT(*) FROM conta_cliente WHERE cliente_id IS NULL"
    )
    logger.warning(
        "Regra 5: %d contas sem cliente_id recuperadas pelo CNPJ raiz; %d sem cliente.",
        recuperadas,
        sem_cliente,
    )

    divergente_crm = _escalar(
        conexao,
        "SELECT COUNT(*) FROM conta_cliente cc JOIN crm_clientes c ON c.cliente_id = cc.cliente_id_informado "
        "WHERE REGEXP_REPLACE(CAST(c.cnpj_raiz AS VARCHAR), '[^0-9]', '', 'g') <> cc.cnpj_raiz",
    )
    if divergente_crm:
        logger.error(
            "ANOMALIA NOVA: %d contas com cliente_id informado e CNPJ diferente do CRM.",
            divergente_crm,
        )

    for nome in ("fato_consumo_diario", "fato_fatura", "fato_credito"):
        sem_vigencia = sum(
            1 for f in tabelas[nome] if f["sk_cliente"] == SK_CLIENTE_NAO_VINCULADO
        )
        logger.warning(
            "Regra 6: %d linhas de %s sem versão de cliente vigente na data (sk_cliente = -1).",
            sem_vigencia,
            nome,
        )

    com_mascara = _escalar(
        conexao,
        "SELECT COUNT(*) FROM conta_normalizada WHERE cnpj_raiz_original <> cnpj_raiz",
    )
    fora_do_padrao = _escalar(
        conexao, "SELECT COUNT(*) FROM conta_normalizada WHERE LENGTH(cnpj_raiz) <> 8"
    )
    logger.warning(
        "CNPJ: %d contas com máscara normalizadas para 8 dígitos.", com_mascara
    )
    if fora_do_padrao:
        logger.error(
            "ANOMALIA NOVA: %d CNPJs raiz sem 8 dígitos após normalizar.",
            fora_do_padrao,
        )

    produtos_multi_unidade = _escalar(
        conexao,
        "SELECT COUNT(*) FROM (SELECT produto FROM dim_produto GROUP BY produto HAVING COUNT(*) > 1)",
    )
    if produtos_multi_unidade:
        logger.error(
            "ANOMALIA NOVA: %d produtos com mais de uma unidade-base.",
            produtos_multi_unidade,
        )


# --------------------------------------------------------------------------
# Entrada principal
# --------------------------------------------------------------------------
def transformar(pasta_dados: Path) -> dict[str, list[dict]]:
    """Lê os CSVs de pasta_dados e devolve as linhas de cada tabela do schema dw."""
    conexao = duckdb.connect()
    # Fuso fixo: garante o mesmo cálculo de datas/horas em qualquer máquina.
    conexao.sql("SET TimeZone = 'UTC'")

    # Cada CSV vira uma view com o nome do arquivo (ex.: faturas, consumo_diario).
    for caminho_csv in sorted(pasta_dados.glob("*.csv")):
        ler_csv(conexao, caminho_csv).create_view(caminho_csv.stem, replace=True)

    _criar_views_dimensoes(conexao)

    tabelas: dict[str, list[dict]] = {
        "dim_data": _linhas(conexao.sql("SELECT * FROM dim_data ORDER BY sk_data")),
        "dim_conta": _linhas(conexao.sql("SELECT * FROM dim_conta ORDER BY sk_conta")),
        "dim_cliente": _linhas(
            conexao.sql("SELECT * FROM dim_cliente ORDER BY sk_cliente")
        ),
        "dim_produto": _linhas(
            conexao.sql("SELECT * FROM dim_produto ORDER BY sk_produto")
        ),
        "dim_regiao": _linhas(
            conexao.sql("SELECT * FROM dim_regiao ORDER BY sk_regiao")
        ),
    }
    # Membro "Não vinculado" (conta sem cliente ou sem versão vigente na data do evento).
    tabelas["dim_cliente"].insert(
        0,
        {
            "sk_cliente": SK_CLIENTE_NAO_VINCULADO,
            "cliente_id": "N/D",
            "segmento": "Não vinculado",
            "canal": None,
            "uf": None,
            "valido_de": date(1900, 1, 1),
            "valido_ate": FIM_VIGENCIA,
        },
    )

    tabelas["fato_consumo_diario"] = _fato_consumo_diario(conexao)
    tabelas["fato_fatura"] = _fato_fatura(conexao)
    tabelas["fato_credito"] = _fato_credito(conexao)
    tabelas["fato_ticket"] = _fato_ticket(conexao)

    _registrar_anomalias(conexao, tabelas)
    return tabelas
