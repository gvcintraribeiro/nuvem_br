"""Configuração da conexão com o Postgres, lida de variáveis de ambiente."""

import os
from pathlib import Path

from sqlalchemy.engine import URL

# Os padrões são os do docker-compose.yml (ambiente local de desenvolvimento).
# Em outros ambientes, defina as variáveis NUVEM_PG_* e não use o padrão.
PG_HOST = os.environ.get("NUVEM_PG_HOST", "localhost")
PG_PORT = int(os.environ.get("NUVEM_PG_PORT", "5432"))
PG_USER = os.environ.get("NUVEM_PG_USER", "nuvem")
PG_PASSWORD = os.environ.get("NUVEM_PG_PASSWORD", "nuvem_local")
PG_DATABASE = os.environ.get("NUVEM_PG_DATABASE", "nuvem_br")

# Schema do modelo dimensional, separado do DDL de referência (public).
SCHEMA_DW = "dw"

PASTA_DADOS = Path(os.environ.get("NUVEM_DADOS", "data"))

# Scripts SQL da camada de consumo (views do schema mart). Fica em subpasta para não
# ser executado pelo initdb do container (que só lê os .sql da raiz de sql/).
# O caminho é relativo a este arquivo, então não depende do diretório de execução.
PASTA_CAMADA_CONSUMO = Path(__file__).parent / "sql" / "camada_consumo"


def url_conexao() -> URL:
    """Monta a URL do SQLAlchemy (URL.create escapa caracteres especiais da senha)."""
    return URL.create(
        "postgresql+psycopg",
        username=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DATABASE,
    )
