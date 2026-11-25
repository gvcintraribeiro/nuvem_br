"""Checagens de qualidade e reconciliação sobre as tabelas já carregadas no dw.

Cada checagem imprime PASSOU ou FALHOU. As referências (91.098 linhas, R$ 16,72 mi etc.)
são os critérios de aceite combinados para este case.
"""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from nuvem_br.config import SCHEMA_DW
from nuvem_br.models import Base

LINHAS_CONSUMO_ESPERADAS = 91_098  # 91.396 do CSV - 298 duplicadas por lote
MILHOES_CONSUMO = Decimal("16.72")
MILHOES_FATURADO = Decimal("16.62")
CONTAS_DIVERGENTES = {"B-00005", "B-00013", "B-00059", "B-00092"}
DIFERENCA_RECONCILIACAO = Decimal("102771")
CREDITOS_ESPERADOS = Decimal("105190.83")
TOLERANCIA_RECONCILIACAO = Decimal("0.005")  # 0,5% do valor medido
COMPETENCIA_INICIAL_DIVERGENCIA = "2026-06"


def _resultado(nome: str, passou: bool, detalhe: str) -> bool:
    print(f"{'PASSOU' if passou else 'FALHOU'} - {nome} ({detalhe})")
    return passou


def _escalar(conexao: Connection, sql: str):
    return conexao.execute(text(sql)).scalar()


def _checar_linhas_consumo(conexao: Connection) -> bool:
    linhas = _escalar(conexao, f"SELECT COUNT(*) FROM {SCHEMA_DW}.fato_consumo_diario")
    return _resultado(
        "fato_consumo_diario com 91.098 linhas",
        linhas == LINHAS_CONSUMO_ESPERADAS,
        f"obtido {linhas:,}".replace(",", "."),
    )


def _checar_soma_consumo(conexao: Connection) -> bool:
    total = _escalar(
        conexao, f"SELECT SUM(valor_medido) FROM {SCHEMA_DW}.fato_consumo_diario"
    )
    return _resultado(
        "soma de valor_medido ≈ R$ 16,72 milhões",
        round(total / 1_000_000, 2) == MILHOES_CONSUMO,
        f"obtido R$ {total:,.2f}",
    )


def _checar_soma_faturado(conexao: Connection) -> bool:
    total = _escalar(
        conexao,
        f"SELECT SUM(valor_bruto) FROM {SCHEMA_DW}.fato_fatura WHERE status <> 'CANCELADA'",
    )
    return _resultado(
        "soma de valor_bruto das faturas (sem canceladas) ≈ R$ 16,62 milhões",
        round(total / 1_000_000, 2) == MILHOES_FATURADO,
        f"obtido R$ {total:,.2f}",
    )


def _checar_reconciliacao(conexao: Connection) -> bool:
    """Medido x faturado por conta e mês; divergente = diferença > 0,5% do medido."""
    linhas = conexao.execute(text(f"""
            WITH medido AS (
                SELECT c.conta_id, d.competencia, SUM(f.valor_medido) AS valor_medido
                FROM {SCHEMA_DW}.fato_consumo_diario f
                JOIN {SCHEMA_DW}.dim_conta c ON c.sk_conta = f.sk_conta
                JOIN {SCHEMA_DW}.dim_data d ON d.sk_data = f.sk_data
                GROUP BY c.conta_id, d.competencia
            ),
            faturado AS (
                SELECT c.conta_id, d.competencia, SUM(f.valor_bruto) AS valor_faturado
                FROM {SCHEMA_DW}.fato_fatura f
                JOIN {SCHEMA_DW}.dim_conta c ON c.sk_conta = f.sk_conta
                JOIN {SCHEMA_DW}.dim_data d ON d.sk_data = f.sk_data_competencia
                WHERE f.status <> 'CANCELADA'
                GROUP BY c.conta_id, d.competencia
            )
            SELECT
                COALESCE(m.conta_id, f.conta_id) AS conta_id,
                COALESCE(m.competencia, f.competencia) AS competencia,
                COALESCE(f.valor_faturado, 0) - COALESCE(m.valor_medido, 0) AS diferenca,
                COALESCE(m.valor_medido, 0) AS valor_medido
            FROM medido m
            FULL JOIN faturado f
                ON f.conta_id = m.conta_id AND f.competencia = m.competencia
            """)).all()

    divergentes = [
        l
        for l in linhas
        if abs(l.diferenca) > TOLERANCIA_RECONCILIACAO * l.valor_medido
    ]
    contas = {l.conta_id for l in divergentes}
    primeira = min((l.competencia for l in divergentes), default="")
    soma = abs(sum((l.diferenca for l in divergentes), Decimal(0)))

    ok = (
        contas == CONTAS_DIVERGENTES
        and primeira >= COMPETENCIA_INICIAL_DIVERGENCIA
        and round(soma) == DIFERENCA_RECONCILIACAO
    )
    return _resultado(
        "reconciliação por conta e mês: só 4 contas divergem, de jun/2026, ≈ R$ 102.771",
        ok,
        f"contas {sorted(contas)}, desde {primeira}, diferença R$ {soma:,.2f}",
    )


def _checar_creditos(conexao: Connection) -> bool:
    total = _escalar(conexao, f"SELECT SUM(valor) FROM {SCHEMA_DW}.fato_credito")
    return _resultado(
        "soma de fato_credito.valor ≈ R$ 105.190,83",
        abs(total - CREDITOS_ESPERADOS) < Decimal("0.01"),
        f"obtido R$ {total:,.2f}",
    )


def _checar_fks_orfas(conexao: Connection) -> bool:
    """Conta, para cada FK de cada fato, as linhas sem correspondente na dimensão."""
    orfas: dict[str, int] = {}
    for tabela in Base.metadata.sorted_tables:
        for fk in tabela.foreign_keys:
            coluna, alvo = fk.parent.name, fk.column
            quantidade = _escalar(
                conexao,
                f"""
                SELECT COUNT(*) FROM {tabela.fullname} t
                LEFT JOIN {alvo.table.fullname} d ON d.{alvo.name} = t.{coluna}
                WHERE t.{coluna} IS NOT NULL AND d.{alvo.name} IS NULL
                """,
            )
            if quantidade:
                orfas[f"{tabela.name}.{coluna}"] = quantidade
    return _resultado(
        "nenhuma FK órfã em nenhum fato",
        not orfas,
        f"órfãs: {orfas}" if orfas else "0 órfãs",
    )


def _avisar_creditos_x_faturas(conexao: Connection) -> None:
    """Informativo (não reprova): créditos das faturas x tabela de créditos."""
    divergentes = conexao.execute(text(f"""
            WITH fat AS (
                SELECT sk_conta, sk_data_competencia, SUM(valor_creditos) AS valor
                FROM {SCHEMA_DW}.fato_fatura
                WHERE status <> 'CANCELADA'
                GROUP BY sk_conta, sk_data_competencia
            ),
            cre AS (
                SELECT sk_conta, sk_data_competencia, SUM(valor) AS valor
                FROM {SCHEMA_DW}.fato_credito
                GROUP BY sk_conta, sk_data_competencia
            )
            SELECT COUNT(*)
            FROM fat
            FULL JOIN cre USING (sk_conta, sk_data_competencia)
            WHERE COALESCE(fat.valor, 0) <> COALESCE(cre.valor, 0)
            """)).scalar()
    print(
        f"AVISO - {divergentes} combinações conta x competência com crédito divergente entre fatura e creditos"
    )


def validar(engine: Engine) -> bool:
    """Roda todas as checagens; devolve True se todas passaram."""
    with engine.connect() as conexao:
        resultados = [
            _checar_linhas_consumo(conexao),
            _checar_soma_consumo(conexao),
            _checar_soma_faturado(conexao),
            _checar_reconciliacao(conexao),
            _checar_creditos(conexao),
            _checar_fks_orfas(conexao),
        ]
        _avisar_creditos_x_faturas(conexao)
    return all(resultados)
