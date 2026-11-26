# Prompts de maior impacto

Seleção dos prompts que mudaram o rumo ou o resultado do projeto. A referência (ex.: 2.38) aponta para a interação correspondente em [conversas_copilot.md](conversas_copilot.md). Os trechos são citações dos prompts originais.

## 1. Definiram o padrão do código (valem para todos os estudos)

| Ref. | Prompt (trecho) | Impacto |
|---|---|---|
| 2.2 | "preciso que seja um arquivo com essa estrutura: Arquivos `.py` com células `# %%` são melhor rastreados pelo Git" | Todos os estudos de `exploracao_erro_bases/` seguem o formato de células `# %%`, com diffs legíveis no Git. |
| 2.4 | "função que leia meus arquivos CSVs. Após essa função ser criada, preciso que chame ela para cada arquivo e guarde em uma variável. O código deve ser bem simples e sem muitas validações" | Originou `ler_csv` e `dados_por_arquivo`, a base de todos os estudos. Também tirou o `if __name__ == "__main__"`. |
| 2.6 | Erro colado: `'pandas' is required for this operation` (por causa do `.df()`) | Virou convenção do projeto: DuckDB com `read_csv_auto(?)` e `params`, sem pandas e sem `.df()`. |

## 2. Geraram os achados de qualidade (base do relatório de anomalias)

| Ref. | Prompt (trecho) | Impacto |
|---|---|---|
| 2.18 e 2.19 | "utilizando REGEX, que arrume os CNPJs para ficarem apenas com 8 números... pode apenas arrumar o CNPJ, comparar com a base de crm_clientes e pegar o client_id de lá" | Mostrou que as 6 contas sem `cliente_id` são recuperáveis pelo CNPJ raiz normalizado e que há 2 CNPJs com máscara. |
| 2.20 | "comparando o cliente_id da base nova com a base antiga, a fim de ver se erram apenas os nulos... ou tinha algum preenchido errado" | Resultado: 6 nulos, 87 corretos e 0 incorretos. O único problema é preenchimento, não vínculo errado. |
| 2.28 e 2.29 | "pode ignorar o valor_credito = 0 da fatura" e "pode ignorar todos pedidos com status igual a CANCELADA" | A regra de excluir canceladas passou a valer em tudo e reduziu as divergências fatura × crédito de 3 para 1 (B-00082, 2026-01). |
| 2.31 | "compara se todos os créditos do tipo SLA... têm um ticket do tipo Indisponibilidade associado ao conta_id" | Achou 7 dos 14 créditos SLA sem ticket (CR-00060 a CR-00065 e CR-00067), um risco de controle e de receita. |

## 3. Estruturaram a solução (modelo, pipeline e camada de consumo)

| Ref. | Prompt (trecho) | Impacto |
|---|---|---|
| 2.32 | "Eu tenho arquivo PDF com instrução de tudo que tenho que fazer... gostaria que ele tivesse acesso em seu contexto, por meio de um arquivo .md" | Criou o `.github/copilot-instructions.md`: o enunciado do case e as convenções passaram a valer em toda conversa. |
| 2.38 | Especificação do star schema: 4 fatos e 5 dimensões com o grão de cada um, SCD2 em `dim_cliente`, 6 regras de tratamento (lotes duplicados, TB-dia × 1024, canceladas, `valor_liquido` invertido, contas sem cliente, `sk_cliente` válido na data do evento), critérios de aceite numéricos e "primeiro me mostre um plano curto e espere minha confirmação" | Prompt de maior impacto. Gerou `models.py`, `transform.py`, `load.py`, `validate.py` e o `main.py` orquestrador. Os critérios numéricos viraram as checagens de `validate.py`. |
| 2.39 | "Pode já recuperar pelo CNPJ / Deixe os CNPJs todos arrumados / Pode ser Truncate" | Resolveu as decisões abertas do plano: recuperação do cliente pelo CNPJ, CNPJs limpos e carga idempotente com `TRUNCATE`. |
| 2.40 | "ok pode avançar" | Liberou a camada de consumo: as views do schema `mart` em `sql/camada_consumo/01_views_diretoria.sql`. |
| 3.1 | "Na dim data... adicionar colunas com o número do mês, nome do mês, trimestre, dia da semana, número do dia da semana, dia do ano" | Enriqueceu `dim_data` para as análises por período no painel. |

## 4. Entregáveis para a diretoria e a documentação

| Ref. | Prompt (trecho) | Impacto |
|---|---|---|
| 3.3 | "Crie um README.md... ferramentas e libs... explique o estudo começou por uma análise no Google Sheets integrado ao Gemini..." | README com o fluxo do estudo, a stack e o diagrama do star schema. |
| 3.4 | "crie um relatório em .md executivo achando de 3 a 5 achados nas consultas das views... onde estamos ganhando dinheiro e onde estamos perdendo... conclua se estamos crescendo ou não" | Relatório executivo para a diretoria, com a conclusão sobre o crescimento da receita. |
| 4.4, 4.5 e 4.7 | "o que eu posso incluir na minha stack para fazer uma linhagem dos dados... como o dbt faz?" e "Faça uma documentação de um dicionário de dados partindo das tabelas em CSV... e a linhagem até as views" | Entregou a tarefa 4 (dicionário e linhagem) em Markdown, versionável no GitHub. |

## 5. Visões e painel (BI)

| Ref. | Prompt (trecho) | Impacto |
|---|---|---|
| 6.2 | "Baseado em todo o estudo até aqui e a estrutura do DW. Me ajude agora com sugestões de indicadores e visões, que seriam importantes mostrar diariamente para a diretoria" | Definiu os KPIs e as páginas do painel (crescimento, perda de receita, confiabilidade, clientes). |
| 6.3 e 6.4 | "quais ferramentas de BI se encaixariam bem nesse projeto?" e "vou testar o metabase conectado ao docker" | Escolheu o Metabase no `docker-compose.yml`, lendo o schema `mart`. |
| 6.9 e seguintes | "Crie uma pasta chamada metabase... arquivos sql preparados para as seguintes visões" (receita, % de créditos, MoM, inadimplência; depois clientes e consumo) | Criou as consultas prontas para o Metabase em `metabase/estudo_receita`, `estudo_clientes` e `estudo_consumo`, todas retirando faturas canceladas. |

## Padrão que se repete nos prompts eficazes

- **Pedir um plano antes do código** (2.38) evitou retrabalho e levou às decisões de 2.39.
- **Fixar a regra de negócio no prompt** (ignorar canceladas, valor de crédito > 0, critérios de aceite numéricos) deu resultados verificáveis.
- **Colar o erro real** (2.6) transformou um problema pontual em uma convenção do projeto.
