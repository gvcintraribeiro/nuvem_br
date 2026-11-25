# NuvemBR: relatório executivo de receita (jan a out/2026)

Fonte: views do schema `mart` (`sql/camada_consumo/01_views_diretoria.sql`). Valores em R$. Receita faturada considera apenas faturas não canceladas; "líquido" = bruto − créditos.

## Resposta direta

**Estamos crescendo, e rápido.** A receita líquida faturada passou de R$ 1,24 mi (jan) para R$ 2,50 mi (out): **+101% em 9 meses, ou cerca de 8,1% ao mês** (taxa composta). O 3º trimestre faturou 22,6% a mais que o 2º. Em 7 dos 9 meses a receita subiu sobre o mês anterior.

Dois pontos de atenção: o crescimento vem de clientes que já temos (a base parou de crescer em set/out) e há receita medida que não está chegando à fatura, em valor crescente.

| Mês | Receita líquida (R$ mil) | Variação sobre o mês anterior |
|---|---:|---:|
| jan | 1.242 | n/a |
| fev | 1.192 | −4,1% |
| mar | 1.500 | +25,9% |
| abr | 1.384 | −7,8% |
| mai | 1.542 | +11,4% |
| jun | 1.606 | +4,2% |
| jul | 1.639 | +2,1% |
| ago | 1.894 | +15,5% |
| set | 2.022 | +6,8% |
| out | 2.496 | +23,5% |

As quedas de fev e abr são pontuais e foram recuperadas no mês seguinte. A tendência é de alta, com aceleração desde agosto.

## Achados

### 1. A receita dobrou em 9 meses

- Líquido: R$ 1,24 mi → R$ 2,50 mi (+101%). Bruto faturado: +101,6% no mesmo período.
- Consumo medido (o que o cliente realmente usou): R$ 1,25 mi → R$ 2,55 mi (+104%).
- Acumulado jan a out: R$ 16,5 mi líquidos.

### 2. Onde ganhamos: Enterprise e computação

**Por segmento (receita líquida, out/2026):**

| Segmento | Receita out (R$ mil) | % do total | Crescimento jan a out |
|---|---:|---:|---:|
| Enterprise (14 clientes) | 1.551 | 62% | +91% |
| Mid (28 clientes) | 723 | 29% | +123% |
| SMB (39 clientes) | 222 | 9% | +111% |

- 14 clientes Enterprise respondem por 62% da receita (ticket médio de ~R$ 112 mil/mês contra ~R$ 26 mil no Mid e ~R$ 6 mil no SMB). É a nossa maior fonte de receita e também uma concentração de risco.
- O Mid é o que mais cresce e ganhou participação (26% → 29%).

**Por produto (consumo medido):**

| Produto | % da receita em jan | % da receita em out | Crescimento jan a out |
|---|---:|---:|---:|
| VM_COMPUTE | 42,0% | 46,1% | +124% |
| KUBERNETES | 4,5% | 5,2% | +133% |
| BLOCK_STORAGE | 14,0% | 13,9% | +103% |
| OBJECT_STORAGE | 11,8% | 11,6% | +100% |
| EGRESS | 20,3% | 17,1% | +72% |
| DATABASE | 7,3% | 6,0% | +68% |

Computação (VM + Kubernetes) é o motor: 51% da receita e as maiores taxas de crescimento. Egress e Database crescem abaixo da média e perdem participação.

### 3. O crescimento vem de quem já é cliente, não de clientes novos

- Clientes ativos: 65 (jan) → 85 (pico em ago) → **81 (out)**.
- Em set e out **nenhum cliente novo** começou a consumir; saíram 3 em set e 1 em out. Nos 9 meses: 25 novos e 9 perdidos.
- Receita medida por cliente ativo: R$ 19,2 mil → R$ 31,4 mil (+64%).

Ou seja, o aumento recente é expansão de consumo da base atual. É um bom sinal de adoção, mas crescer só por expansão tem limite e aumenta a dependência dos grandes clientes. Se a aquisição continuar parada, o ritmo de out (+23%) dificilmente se sustenta.

### 4. Onde perdemos: 4 contas faturadas 10% a 14% abaixo do que consumiram

- Até maio, medido e faturado batiam (diferença inferior a 0,01%). **A partir de jun**, quatro contas passaram a ser faturadas abaixo do medido, de forma constante:

| Conta | Diferença em out (R$) | % abaixo do medido |
|---|---:|---:|
| B-00013 | −15.872 | 10,5% |
| B-00059 | −9.853 | 12,1% |
| B-00005 | −1.801 | 14,3% |
| B-00092 | −321 | 12,5% |

- Acumulado jun a out: **R$ 102,8 mil não faturados**. O valor mensal subiu de R$ 16,2 mil (jun) para R$ 27,8 mil (out) e vai crescer junto com o consumo dessas contas.
- No ritmo de out, são cerca de **R$ 334 mil por ano**. As duas maiores contas (B-00013 e B-00059) somam 92% do problema.
- Um percentual quase fixo por conta, com início na mesma data, sugere causa sistemática (parametrização de preço ou desconto não registrado na fatura), e não erro aleatório. A causa precisa ser confirmada com o time de Billing; o detalhamento está no relatório de anomalias.

### 5. Créditos são pequenos no total, mas o de SLA em outubro e sua origem merecem revisão

- Total de créditos: R$ 105 mil, **0,63% do faturamento bruto**. Não é um vazamento relevante hoje.
- Composição: promocionais R$ 52,6 mil (50%), SLA R$ 35,7 mil (34%), comerciais R$ 16,9 mil (16%).
- Em out, dois créditos de SLA somaram **R$ 21,1 mil**, contra no máximo R$ 4,4 mil em qualquer mês anterior.
- Pelas validações já feitas, 7 dos 14 créditos de SLA não têm chamado de indisponibilidade na mesma conta. Há compensação sendo concedida sem evidência no suporte.

## Recomendações

| # | Ação | Dono sugerido | Impacto |
|---|---|---|---|
| 1 | Corrigir a fatura das contas B-00013, B-00059, B-00005 e B-00092 e avaliar refaturamento de jun a out | Billing / Financeiro | Recuperar até R$ 102,8 mil e evitar ~R$ 28 mil/mês |
| 2 | Criar alerta mensal de diferença medido × faturado acima de 0,5% por conta | Dados | Evitar nova perda silenciosa |
| 3 | Retomar a aquisição de clientes (zero novos em set/out) e acompanhar os 4 clientes perdidos em set/out | Comercial / Customer Success | Sustentar o crescimento além da expansão da base |
| 4 | Plano de relacionamento para os 14 Enterprise (62% da receita) | Customer Success | Reduzir risco de concentração |
| 5 | Exigir ticket de indisponibilidade para conceder crédito de SLA e revisar os 7 sem evidência | Suporte / Billing | Controle de créditos |

## Premissas e limites

- **Receita** = valor faturado em faturas não canceladas, por competência. Consumo medido = quantidade × preço unitário, após remover lotes duplicados do pipeline de medição.
- **Cliente ativo** = cliente com consumo medido maior que zero no mês; várias contas do mesmo cliente contam uma vez. "Novo" é o primeiro mês com consumo, "perdido" é quem consumiu no mês anterior e não consumiu no atual (pode ser pausa e não cancelamento).
- **Segmento** é o vigente na data da fatura (histórico preservado). Jan não tem cliente "novo" real: inclui toda a base existente.
- **Crescimento composto** = $(2{,}496 / 1{,}242)^{1/9} − 1 \approx 8{,}1\%$ ao mês. Não deve ser extrapolado para o ano: a série tem só 10 meses e out foi atípico.
- Não há dados de custo, então "ganhar" e "perder" estão medidos em **receita**, não em margem. Produtos com maior receita podem não ser os mais rentáveis.
- Os efeitos de dias por mês (fev com 28 dias) explicam parte das oscilações mensais; não foram ajustados.
