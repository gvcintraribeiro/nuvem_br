# Contexto do projeto: Case Técnico – Analista de Dados Sênior (NuvemBR)

Este arquivo é carregado automaticamente pelo Copilot como contexto. Ele resume o enunciado do case e as convenções do projeto.

## Contexto

NuvemBR é uma provedora fictícia de nuvem pública que vende computação, armazenamento, banco de dados e Kubernetes por consumo, em reais, para empresas de todos os portes. Empresa, clientes, produtos e números são inteiramente fictícios.

Pedido da diretoria:

> "Precisamos saber se estamos crescendo de forma saudável e onde estamos perdendo receita. Hoje cada área traz um número diferente de faturamento e ninguém confia no painel atual. Queremos uma visão única e confiável para a reunião de diretoria."

Não há lista de perguntas fechada. Parte do desafio é traduzir o pedido em KPIs, registrar as premissas assumidas e decidir o que priorizar. Se algo for ambíguo: decidir, registrar a decisão e seguir em frente.

## Dados fornecidos

7 CSVs em `data/`, extraídos de três sistemas não integrados, cobrindo **jan a out/2026**. São extrações brutas: **não assumir que estão corretos**. Engine usado no projeto: **DuckDB**. O DDL de referência está em `sql/00_ddl_postgres.sql`.

| Arquivo | Sistema | Grão | Linhas |
|---|---|---|---|
| `crm_clientes.csv` | CRM | 1 linha por cliente (segmento atual) | 90 |
| `crm_segmento_historico.csv` | CRM | 1 linha por cliente e período de vigência do segmento | 98 |
| `billing_contas.csv` | Billing | 1 linha por conta de faturamento | 93 |
| `consumo_diario.csv` | Medição (pipeline diário) | dia × conta × produto × lote de carga | 91.396 |
| `faturas.csv` | Billing | 1 linha por fatura emitida | 785 |
| `creditos.csv` | Billing | 1 linha por crédito concedido | 80 |
| `tickets.csv` | Suporte | 1 linha por chamado | 371 |

Regras de origem:

- **Cliente x conta:** um cliente do CRM pode ter mais de uma conta de faturamento. O vínculo `billing_contas.cliente_id` é preenchido manualmente pelo time comercial.
- **Receita de consumo:** `quantidade × preco_unitario`. O preço é sempre por unidade-base do produto (vCPU-hora, GB-dia, nó-hora, instância-hora ou GB).
- **Pipeline de medição:** roda diariamente e grava o identificador do lote em `lote_id` e o horário da carga em `carregado_em`.
- **Faturas:** `valor_liquido = valor_bruto − valor_creditos`. Faturas podem ser canceladas e reemitidas.
- **Créditos:** `PROMOCIONAL` (campanha para clientes novos), `SLA` (compensação por indisponibilidade) ou `COMERCIAL` (desconto negociado).
- **Tickets:** exportados pela ferramenta de suporte.

## Tarefas

O escopo é propositalmente maior que o tempo disponível. Priorizar e explicar no relatório o que ficou de fora e por quê. As tarefas 1 a 4 são esperadas; a 5 é diferencial.

1. **Modelagem dimensional.** Propor o star schema que sustenta a visão pedida. Definir o grão de cada fato, as dimensões e como tratar mudanças de atributos ao longo do tempo. Entregar diagrama simples e justificativa.
2. **Camada de consumo em SQL.** Implementar o modelo e as métricas para responder à diretoria. SQL comentado, explicando o que cada etapa faz e por quê.
3. **Qualidade e reconciliação.** Investigar a confiabilidade dos dados. Reconciliar consumo medido × faturado × créditos. Entregar relatório de anomalias com: problema, evidência (query), impacto estimado em R$, tratamento aplicado e time que deve corrigir na origem.
4. **Dicionário e linhagem.** Documentar as métricas entregues: definição de negócio, fórmula, tabelas de origem e regras aplicadas.
5. **Diferencial: automação.** Mostrar como garantir que testes de qualidade e atualização rodem todo dia sem intervenção manual (dbt tests, Airflow, cron ou script Python). Pode ser implementado ou descrito.

## Entregáveis (prazo: 72 horas)

| Item | Formato | Observação |
|---|---|---|
| Scripts SQL (tarefas 2 e 3) | `.sql` comentado | Indicar o engine usado |
| Modelo dimensional | Imagem ou PDF | Com o grão de cada fato explícito |
| Relatório executivo | PDF, até 3 páginas | 3 a 5 achados, recomendações e premissas |
| Relatório de anomalias | Planilha ou PDF | Problema, evidência, impacto em R$, tratamento, dono |
| Dicionário e linhagem | Planilha, Markdown ou similar | Para as métricas entregues |
| Painel executivo | Link ou print + arquivo, 1 página | Qualquer BI; documentar a lógica das medidas |
| Log de uso de IA | PDF ou Markdown, até 1 página | Ver abaixo |
| Automação (opcional) | Código ou descrição | Tarefa 5 |

Etapa ao vivo (60 min, por vídeo): apresentação de 10 min como se fosse para a diretoria, seguida de perguntas técnicas e de carreira. Cada decisão precisa ser compreendida e defendida pelo candidato.

## Uso de IA

O uso de IA é permitido e esperado. O log de uso de IA (máx. 1 página) deve conter:

- ferramentas usadas e em quais tarefas;
- os 3 a 5 prompts mais importantes;
- o que foi aceito, corrigido ou descartado, e por quê;
- como os números foram verificados.

## Convenções do projeto (para o Copilot seguir)

- Idioma: português nos comentários, nomes de variáveis e textos.
- Engine: DuckDB, com `read_csv_auto(?)` e parâmetros (`params=[...]`) em vez de interpolar caminhos no SQL.
- Não usar `.df()` nem pandas (não está instalado).
- Os estudos exploratórios ficam em `exploracao_bases/` e `exploracao_erro_bases/`, em arquivos `.py` com células `# %%` (execução interativa, sem `if __name__ == "__main__"`).
- Estrutura padrão de cada estudo: função `ler_csv`, carga de todos os CSVs de `data/` em `dados_por_arquivo`, depois consultas em células separadas, cada uma com comentário explicando o objetivo.
- Código simples, com poucas validações e sem abstrações desnecessárias.
- Saídas geradas ficam em `outputs/` (já no `.gitignore`, assim como `data/`).
- Nas análises de faturas, ignorar `status = 'CANCELADA'`.

## Achados já levantados (verificados nos dados)

- `crm_segmento_historico`: todos os `cliente_id` existem em `crm_clientes`; o menor `valido_de` é igual a `data_inicio`; o segmento mais recente é igual ao segmento atual do cliente.
- `crm_clientes`: sem `cnpj_raiz` duplicado; há `razao_social` repetida (CNPJs diferentes).
- `billing_contas`: 6 de 93 contas sem `cliente_id` (recuperável pelo CNPJ raiz normalizado); 2 `cnpj_raiz` com máscara (ex.: `75.742.256`) que precisam ser limpos para 8 dígitos; nenhum `cliente_id` preenchido incorretamente.
- `faturas` (sem canceladas): sem `fatura_id` duplicado; 1 divergência de crédito contra `creditos.csv` (conta B-00082, competência 2026-01).
- `creditos` tipo SLA: 14 créditos, 7 sem ticket de Indisponibilidade na mesma conta (CR-00060, CR-00061, CR-00062, CR-00063, CR-00064, CR-00065 e CR-00067).
