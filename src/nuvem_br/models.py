"""Modelos SQLAlchemy do star schema (schema dw).

Convenções:
- Dimensões: surrogate key inteira (sk_*) como PK + chave natural única.
  As sk são geradas na carga (transform/load), por isso autoincrement=False.
- Fatos: o grão está descrito na docstring de cada classe.
- Valores monetários e quantidades: NUMERIC(18,4).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nuvem_br.config import SCHEMA_DW

# Valor que representa "vigente" em dim_cliente.valido_ate (facilita o join por período).
FIM_VIGENCIA = date(9999, 12, 31)

# Membro da dim_cliente usado quando a conta não tem cliente (ou o cliente não existe).
SK_CLIENTE_NAO_VINCULADO = -1


def numerico() -> Numeric:
    """Tipo padrão de valores monetários e quantidades."""
    return Numeric(18, 4)


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA_DW)


# --------------------------------------------------------------------------
# Dimensões
# --------------------------------------------------------------------------
class DimData(Base):
    """Calendário. Grão: 1 linha por dia. sk_data = AAAAMMDD."""

    __tablename__ = "dim_data"

    sk_data: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    data: Mapped[date] = mapped_column(Date, unique=True)
    competencia: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    numero_mes: Mapped[int] = mapped_column(Integer)  # 1 a 12
    nome_mes: Mapped[str] = mapped_column(String(10))
    trimestre: Mapped[int] = mapped_column(Integer)  # 1 a 4
    dia_semana: Mapped[str] = mapped_column(String(15))
    numero_dia_semana: Mapped[int] = mapped_column(
        Integer
    )  # ISO: 1 = segunda ... 7 = domingo
    dia_ano: Mapped[int] = mapped_column(Integer)  # 1 a 366


class DimConta(Base):
    """Conta de faturamento (billing_contas). Grão: 1 linha por conta."""

    __tablename__ = "dim_conta"

    sk_conta: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    conta_id: Mapped[str] = mapped_column(String(10), unique=True)
    cnpj_raiz: Mapped[str] = mapped_column(String(8))  # normalizado: 8 dígitos
    data_criacao: Mapped[date] = mapped_column(Date)


class DimCliente(Base):
    """Cliente do CRM, SCD tipo 2 no segmento.

    Grão: 1 linha por cliente e período de vigência do segmento.
    canal e uf são tipo 1 (valor atual, repetido em todas as versões).
    sk_cliente = -1 é o membro "Não vinculado".
    """

    __tablename__ = "dim_cliente"
    __table_args__ = (UniqueConstraint("cliente_id", "valido_de"),)

    sk_cliente: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    cliente_id: Mapped[str] = mapped_column(String(10))
    segmento: Mapped[str | None] = mapped_column(String(20))
    canal: Mapped[str | None] = mapped_column(String(20))
    uf: Mapped[str | None] = mapped_column(String(2))
    valido_de: Mapped[date] = mapped_column(Date)
    valido_ate: Mapped[date] = mapped_column(Date)  # 9999-12-31 = vigente


class DimProduto(Base):
    """Produto. Grão: 1 linha por produto, com a unidade-base de cobrança."""

    __tablename__ = "dim_produto"

    sk_produto: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    produto: Mapped[str] = mapped_column(String(20), unique=True)
    unidade_base: Mapped[str] = mapped_column(String(20))


class DimRegiao(Base):
    """Região. Grão: 1 linha por região."""

    __tablename__ = "dim_regiao"

    sk_regiao: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    regiao: Mapped[str] = mapped_column(String(20), unique=True)


# --------------------------------------------------------------------------
# Fatos
# --------------------------------------------------------------------------
class FatoConsumoDiario(Base):
    """Grão: dia x conta x produto x região (já sem lotes duplicados)."""

    __tablename__ = "fato_consumo_diario"
    __table_args__ = (
        # O índice da PK já cobre sk_data; os demais FKs ganham índice próprio.
        Index("ix_fato_consumo_sk_conta", "sk_conta"),
        Index("ix_fato_consumo_sk_cliente", "sk_cliente"),
        Index("ix_fato_consumo_sk_produto", "sk_produto"),
        Index("ix_fato_consumo_sk_regiao", "sk_regiao"),
    )

    sk_data: Mapped[int] = mapped_column(
        ForeignKey("dim_data.sk_data"), primary_key=True
    )
    sk_conta: Mapped[int] = mapped_column(
        ForeignKey("dim_conta.sk_conta"), primary_key=True
    )
    sk_produto: Mapped[int] = mapped_column(
        ForeignKey("dim_produto.sk_produto"), primary_key=True
    )
    sk_regiao: Mapped[int] = mapped_column(
        ForeignKey("dim_regiao.sk_regiao"), primary_key=True
    )
    sk_cliente: Mapped[int] = mapped_column(ForeignKey("dim_cliente.sk_cliente"))
    quantidade_base: Mapped[Decimal] = mapped_column(
        numerico()
    )  # na unidade-base do produto
    valor_medido: Mapped[Decimal] = mapped_column(
        numerico()
    )  # quantidade_base x preco_unitario
    lote_id: Mapped[str] = mapped_column(String(20))  # auditoria


class FatoFatura(Base):
    """Grão: 1 fatura emitida (inclui canceladas e substitutas).

    Receita: filtrar status <> 'CANCELADA'.
    """

    __tablename__ = "fato_fatura"
    __table_args__ = (
        Index("ix_fato_fatura_sk_data_emissao", "sk_data_emissao"),
        Index("ix_fato_fatura_sk_data_competencia", "sk_data_competencia"),
        Index("ix_fato_fatura_sk_conta", "sk_conta"),
        Index("ix_fato_fatura_sk_cliente", "sk_cliente"),
    )

    fatura_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    sk_data_emissao: Mapped[int] = mapped_column(ForeignKey("dim_data.sk_data"))
    sk_data_competencia: Mapped[int] = mapped_column(ForeignKey("dim_data.sk_data"))
    sk_conta: Mapped[int] = mapped_column(ForeignKey("dim_conta.sk_conta"))
    sk_cliente: Mapped[int] = mapped_column(ForeignKey("dim_cliente.sk_cliente"))
    valor_bruto: Mapped[Decimal] = mapped_column(numerico())
    valor_creditos: Mapped[Decimal] = mapped_column(numerico())
    valor_liquido: Mapped[Decimal] = mapped_column(
        numerico()
    )  # recalculado: bruto - créditos
    valor_liquido_origem: Mapped[Decimal] = mapped_column(
        numerico()
    )  # como veio do billing
    status: Mapped[str] = mapped_column(String(20))
    fatura_substituta_id: Mapped[str | None] = mapped_column(String(20))


class FatoCredito(Base):
    """Grão: 1 crédito concedido."""

    __tablename__ = "fato_credito"
    __table_args__ = (
        Index("ix_fato_credito_sk_data_competencia", "sk_data_competencia"),
        Index("ix_fato_credito_sk_conta", "sk_conta"),
        Index("ix_fato_credito_sk_cliente", "sk_cliente"),
    )

    credito_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    sk_data_competencia: Mapped[int] = mapped_column(ForeignKey("dim_data.sk_data"))
    sk_conta: Mapped[int] = mapped_column(ForeignKey("dim_conta.sk_conta"))
    sk_cliente: Mapped[int] = mapped_column(ForeignKey("dim_cliente.sk_cliente"))
    tipo: Mapped[str] = mapped_column(String(20))  # PROMOCIONAL, SLA ou COMERCIAL
    valor: Mapped[Decimal] = mapped_column(numerico())


class FatoTicket(Base):
    """Grão: 1 chamado de suporte."""

    __tablename__ = "fato_ticket"
    __table_args__ = (
        Index("ix_fato_ticket_sk_data_abertura", "sk_data_abertura"),
        Index("ix_fato_ticket_sk_conta", "sk_conta"),
    )

    ticket_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    sk_data_abertura: Mapped[int] = mapped_column(ForeignKey("dim_data.sk_data"))
    sk_conta: Mapped[int] = mapped_column(ForeignKey("dim_conta.sk_conta"))
    severidade: Mapped[str] = mapped_column(String(10))
    categoria: Mapped[str] = mapped_column(String(30))
    horas_resolucao: Mapped[Decimal | None] = mapped_column(numerico())


def criar_tabelas(engine: Engine) -> None:
    """Cria o schema dw e as tabelas, se ainda não existirem."""
    with engine.begin() as conexao:
        conexao.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_DW}"))
    Base.metadata.create_all(engine)
