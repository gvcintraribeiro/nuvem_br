"""Carga idempotente no Postgres.

Estratégia: TRUNCATE de todas as tabelas do schema dw e recarga completa, tudo na mesma
transação. Se algo falhar, nada muda; se rodar duas vezes, o resultado é idêntico (as
surrogate keys são geradas de forma determinística em transform.py).
"""

import logging
from pathlib import Path

from sqlalchemy import insert, text
from sqlalchemy.engine import Engine

from nuvem_br.models import Base

logger = logging.getLogger(__name__)

# Tamanho do lote de INSERT (evita montar uma lista única enorme na memória do driver).
TAMANHO_LOTE = 10_000


def carregar(engine: Engine, tabelas: dict[str, list[dict]]) -> None:
    """Esvazia e recarrega as tabelas do dw. Dimensões antes dos fatos (por causa das FKs)."""
    # sorted_tables respeita a dependência das FKs (dimensões primeiro).
    ordem = [t for t in Base.metadata.sorted_tables if t.name in tabelas]

    with engine.begin() as conexao:
        # Um único TRUNCATE para todas as tabelas: o Postgres aceita porque as FKs
        # ficam todas dentro do mesmo comando.
        nomes = ", ".join(f"{t.schema}.{t.name}" for t in ordem)
        conexao.execute(text(f"TRUNCATE {nomes}"))

        for tabela in ordem:
            linhas = tabelas[tabela.name]
            for inicio in range(0, len(linhas), TAMANHO_LOTE):
                conexao.execute(insert(tabela), linhas[inicio : inicio + TAMANHO_LOTE])
            logger.info("Carregadas %d linhas em %s.", len(linhas), tabela.fullname)


def aplicar_camada_consumo(engine: Engine, pasta_sql: Path) -> None:
    """Executa, em ordem, os .sql da camada de consumo (views com CREATE OR REPLACE)."""
    with engine.begin() as conexao:
        for caminho in sorted(pasta_sql.glob("*.sql")):
            # exec_driver_sql não interpreta ":" do script; o psycopg trata "%" como
            # marcador de parâmetro, então ele é duplicado (%%) antes de executar.
            sql = caminho.read_text(encoding="utf-8").replace("%", "%%")
            conexao.exec_driver_sql(sql)
            logger.info("Camada de consumo aplicada: %s.", caminho.name)
