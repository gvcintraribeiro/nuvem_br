"""Orquestra o pipeline: criar tabelas -> transformar -> carregar -> camada de consumo -> validar."""

import logging
import sys

from sqlalchemy import create_engine

from nuvem_br.config import PASTA_CAMADA_CONSUMO, PASTA_DADOS, url_conexao
from nuvem_br.load import aplicar_camada_consumo, carregar
from nuvem_br.models import criar_tabelas
from nuvem_br.transform import transformar
from nuvem_br.validate import validar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

engine = create_engine(url_conexao())

criar_tabelas(engine)
tabelas = transformar(PASTA_DADOS)
carregar(engine, tabelas)
aplicar_camada_consumo(engine, PASTA_CAMADA_CONSUMO)

# Código de saída 1 se alguma checagem falhar (útil para agendadores como cron/Airflow).
sys.exit(0 if validar(engine) else 1)
