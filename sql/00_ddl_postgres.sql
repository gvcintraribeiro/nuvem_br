-- =====================================================================
-- NuvemBR (empresa fictícia) – DDL de referência (PostgreSQL 15+)
-- Uso opcional: você pode carregar os CSVs em qualquer engine
-- (DuckDB, BigQuery, Postgres, SQLite...). Este DDL reflete o ambiente
-- "de produção" atual da NuvemBR.
-- =====================================================================
CREATE TABLE crm_clientes (
  cliente_id    varchar(10) PRIMARY KEY,
  razao_social  varchar(120),
  cnpj_raiz     varchar(12),
  segmento      varchar(20),   -- segmento ATUAL do cliente
  canal         varchar(20),
  uf            char(2),
  data_inicio   date
);
CREATE TABLE crm_segmento_historico (
  cliente_id  varchar(10),
  segmento    varchar(20),
  valido_de   date,
  valido_ate  date            -- NULL = vigente
);
CREATE TABLE billing_contas (
  conta_id      varchar(10) PRIMARY KEY,
  cliente_id    varchar(10),  -- vínculo com o CRM (preenchimento manual)
  cnpj_raiz     varchar(12),
  data_criacao  date
);
CREATE TABLE consumo_diario (
  data            date,
  conta_id        varchar(10),
  produto         varchar(20),
  regiao          varchar(20),
  quantidade      numeric(18,4),
  unidade         varchar(20),
  preco_unitario  numeric(12,6),
  lote_id         varchar(20),
  carregado_em    timestamp
);
CREATE INDEX ix_consumo_data        ON consumo_diario (data);
CREATE INDEX ix_consumo_conta_data  ON consumo_diario (conta_id, data);

CREATE TABLE faturas (
  fatura_id             varchar(12) PRIMARY KEY,
  conta_id              varchar(10),
  competencia           char(7),      -- 'YYYY-MM'
  valor_bruto           numeric(14,2),
  valor_creditos        numeric(14,2),
  valor_liquido         numeric(14,2),
  status                varchar(12),  -- PAGA | ABERTA | VENCIDA | CANCELADA
  data_emissao          date,
  fatura_substituta_id  varchar(12)
);
CREATE TABLE creditos (
  credito_id   varchar(10) PRIMARY KEY,
  conta_id     varchar(10),
  competencia  char(7),
  tipo         varchar(15),  -- PROMOCIONAL | SLA | COMERCIAL
  valor        numeric(14,2),
  descricao    varchar(120)
);
CREATE TABLE tickets (
  ticket_id     varchar(10) PRIMARY KEY,
  conta_id      varchar(10),
  aberto_em     varchar(25),
  resolvido_em  varchar(25),
  severidade    char(2),
  categoria     varchar(30)
);
