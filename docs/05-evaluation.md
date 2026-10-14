# 5. Avaliação objetiva — execução local

Execução: 2026-10-14T02:09:02Z. Python 3.12.14. Modo **demo**.

Foram executadas 2760 sessões de replay: 23 cenários × seis políticas/ablações × 20 repetições. Há **44 turnos únicos de cliente**, não milhares de exemplos independentes. São 15 cenários de regressão e oito cenários de desafio. As repetições servem para medir tempo, não para aumentar artificialmente evidência de qualidade.

O corpus tem oito documentos fictícios em memória. Os tempos abaixo são medidas reais por perf_counter, em processo Python, com cache misto aquecido e sem rede, fila de produção, ASR ou DOM. Não são valores simulados; tampouco representam um SLA corporativo. Os percentis usam interpolação do NumPy. A ordem das políticas gira entre repetições para reduzir vantagem fixa de cache.

## Resultados das decisões de intervenção

| Política | Conjunto | Precisão da decisão | Cobertura | Desnecessárias entre emitidas | Fonte esperada recuperada* | p50 / p95 / p99 backend (ms) |
|---|---|---:|---:|---:|---:|---|
| A | regression | 51.5% | 100.0% | 48.5% | 100.0% | 0.161 / 0.762 / 1.611 |
| A | challenge | 80.0% | 100.0% | 20.0% | 57.1% | 0.165 / 0.734 / 1.037 |
| B | regression | 73.9% | 100.0% | 26.1% | 100.0% | 0.151 / 0.385 / 0.989 |
| B | challenge | 100.0% | 75.0% | 0.0% | 57.1% | 0.144 / 0.408 / 0.964 |
| C | regression | 100.0% | 100.0% | 0.0% | 100.0% | 0.144 / 0.314 / 0.584 |
| C | challenge | 100.0% | 50.0% | 0.0% | 42.9% | 0.139 / 0.317 / 0.494 |
| C_no_suppression | regression | 73.9% | 100.0% | 26.1% | 100.0% | 0.150 / 0.381 / 0.622 |
| C_no_suppression | challenge | 100.0% | 75.0% | 0.0% | 57.1% | 0.148 / 0.353 / 0.729 |
| C_no_state | regression | 88.9% | 94.1% | 11.1% | 93.8% | 0.148 / 0.327 / 0.647 |
| C_no_state | challenge | 100.0% | 75.0% | 0.0% | 57.1% | 0.143 / 0.395 / 0.807 |
| C_BM25 | regression | 100.0% | 100.0% | 0.0% | 100.0% | 0.143 / 0.331 / 0.597 |
| C_BM25 | challenge | 100.0% | 50.0% | 0.0% | 42.9% | 0.128 / 0.298 / 0.494 |

*Cobertura de fonte entre oportunidades que têm uma fonte esperada; não é uma avaliação de entailment. O desafio de cancelamento de compra proíbe a fonte de cancelamento do cartão, em vez de presumir que seja fraude.

## Interpretação

- C remove o excesso de intervenção nos cenários previstos, mas cobre somente **50% das oportunidades do conjunto de desafio**. A pontuação perfeita na regressão é consequência de um corpus simples, construído junto do protótipo; não comprova generalização.
- Desligar a supressão aumenta cobertura no desafio, com mais ruído na regressão. Há uma fronteira precisão/cobertura que precisa ser calibrada com operadores.
- Mesmo quando decide intervir no momento correto, o sistema pode buscar a política errada. “Cancelar uma compra, não meu cartão” ainda pode levar ao documento de cancelamento de cartão. **Essa falha impede recomendar este detector para produção sem melhoria.**
- A e B usam templates no modo demo. Seus números não representam qualidade de um LLM que poderia decidir abster-se ou interpretar melhor o contexto. Não existe vencedor A/B/C de produção demonstrado nesta entrega.
- Zero chamadas LLM significa zero custo de API nesta execução. Não significa custo operacional total zero.

## Falhas mantidas visíveis — C

| Cenário | Mensagem | Esperado → observado | Fontes emitidas |
|---|---|---|---|
| parafrase | Esse plástico pesa todo mês no bolso; vou largar mão. | intervir → silêncio | — |
| sarcasmo | Excelente, mais uma cobrança que ninguém explica. | intervir → silêncio | — |
| negacao_escopo | Quero cancelar uma compra, não meu cartão. | intervir → interveio | KB-003 |
| novo_detalhe | Como contesto uma anuidade cobrada duas vezes? | intervir → silêncio | — |
| contexto_implicito | E quanto eu pago por ano? | intervir → silêncio | — |

Não foram acrescentadas regras especiais para fazer essas frases de desafio passarem. A próxima versão deve aprender a distinguir objeto do cancelamento, nova necessidade no mesmo assunto e referências implícitas. Durante a verificação corrigimos dois defeitos do fluxo básico: preservação da condução inicial do operador e acionamento do alerta de transação não reconhecida sem ponto de interrogação. Também corrigimos um rótulo de avaliação: pedir explicação da anuidade após esclarecer o produto é uma oportunidade legítima.

## Recuperação: BM25 versus híbrido local

10 unique synthetic queries repeated 30 times. Tiny local in-memory corpus, no network, no embeddings unless a local encoder is configured. No claims about enterprise-scale hybrid search.

| Modo | Cache | Acurácia top-1 | p50 / p95 / p99 (ms) |
|---|---|---:|---|
| bm25 | desabilitado por consulta | 80.0% | 0.021 / 0.028 / 0.060 |
| bm25 | aquecido misto | 80.0% | 0.003 / 0.003 / 0.028 |
| bm25+char_tfidf_rrf | desabilitado por consulta | 80.0% | 0.427 / 0.708 / 0.940 |
| bm25+char_tfidf_rrf | aquecido misto | 80.0% | 0.003 / 0.003 / 0.593 |

Neste microcorpus, BM25 e o híbrido acertam 8/10 consultas top-1. Sem cache, BM25 é mais rápido. **Não há evidência de ganho de qualidade do híbrido neste conjunto**; o caminho simples merece ser o primeiro controle experimental. Isso não autoriza extrapolar para milhões de chunks ou para hybrid search de 600–1.500 ms em uma infraestrutura remota.

O teste sem cache mede computação da consulta sobre índice já carregado, não cold start do processo. Para escala real, separar index initialization, cold/warm retrieval, filtros ACL, tamanho do corpus, top-k, fan-out, fila, rede e reranker. Executar top-k 1/3/5 com as mesmas consultas e fontes relevantes; aumentar ou diminuir top-k só com evidência de fonte suficiente.

## Detectores leves: comparação independente

35 synthetic training examples; 21 separate evaluation phrases; 20 timing repetitions. Only subject classification, not sentiment or complete ontology. Thresholds heuristic, no calibration set. No held-out production data; not evidence to choose a production detector.

| Detector | Macro-F1 de assunto | Taxa unknown | p50 / p95 / p99 (ms) |
|---|---:|---:|---|
| regex | 0.522 | 66.7% | 0.048 / 0.097 / 0.225 |
| bm25_examples | 0.807 | 14.3% | 0.127 / 0.278 / 0.543 |
| char_tfidf_examples | 0.854 | 9.5% | 0.446 / 0.953 / 1.278 |
| linear_classifier | 0.730 | 38.1% | 0.393 / 0.934 / 1.490 |

Há 35 frases sintéticas de treino e 21 frases distintas de teste. Não são exemplos de produção nem um conjunto grande o bastante para escolher definitivamente um detector. O estudo cobre **assunto**, não intenção completa, emoção ou valor de intervenção. TF-IDF por exemplos foi melhor que regex neste conjunto, mas também abstém menos; isso precisa ser confrontado com falsos positivos e dados fora do domínio. O classificador linear não foi ativado automaticamente no runtime. Embeddings semânticos e SLM não foram medidos.

## Métricas, definições e campos ausentes

| Métrica | Definição / implementação | Resultado disponível |
|---|---|---|
| Precisão | TP / (TP + FP), rótulo de oportunidade por turno | Comparação sintética acima |
| Intervenção desnecessária | FP / todas as intervenções emitidas | Acima; distinta de FPR = FP / negativos reais |
| Cobertura | TP / oportunidades rotuladas | Acima, incluindo turnos silenciosos |
| Qualidade/fundamentação | Revisão humana de utilidade e suporte; compatibilidade de fonte é apenas proxy | Campos e UI implementados; avaliação humana não realizada |
| Reuso/aceitação | Cards inseridos no rascunho / cards apresentados | Instrumentado; não medido com operadores |
| Tempo até insight útil | Primeiro card acionável publicado no backend; separadamente double requestAnimationFrame no browser | Backend medido; apresentação no browser sem amostras nesta entrega |
| p50/p95/p99 | Distribuição por política e estágio; população descrita | JSON/CSV e tabela |
| Chamadas LLM | Tentativas iniciadas por mensagem e por insight | Zero reais na execução demo; pedidos potenciais também registrados |
| Tokens | Usage real do Responses API | Não medidos em provedor real |
| Custo estimado | Tokens × preços fornecidos em USD/milhão | Zero de API em demo; live sem preços/usage retorna desconhecido |
| Estado/supressão | Ablações C_no_state e C_no_suppression | Acima |

O frontend mede a partir do envio da mensagem sintética até duas frames após inserir o card, apenas com a página visível e o card presente no DOM. É uma aproximação de apresentação, não uma confirmação de que o operador leu/compreendeu. Nunca misture esses tempos com perf_counter do servidor; os relógios não são comparados diretamente.

## Verificação executada

- 22 testes Python aprovados: estado, isolamento, sequência, idempotência, cancelamento, resolução, privacidade básica, políticas, alerta, recuperação, saída inválida, integração HTTP e contrato do provider com transporte substituído.
- 2 testes do parser SSE aprovados, incluindo UTF-8 dividido entre chunks.
- TypeScript e build Vite aprovados; frontend compilado incluído.
- Um aviso de depreciação na ponte Starlette/httpx durante testes; não houve falha de execução.
- Não executados: inferência OpenAI real, browser QA visual, container build, carga distribuída, embeddings semânticos, ASR, AgentCore ou julgamento humano. Não há valores inventados para preencher essas lacunas.

## Próximo experimento reproduzível

1. Congelar um conjunto independente por conversa e ter dois revisores de domínio rotulando oportunidade, fonte e timing. Resolver divergências sem olhar a política executada.
2. Rodar A/B/C com mesmo modelo, região, corpus e orçamento de saída, registrando token usage, falhas, cancelamentos e cache. Começar com uma repetição real; não extrapolar os tempos demo.
3. Medir condições cold/warm e rajadas concorrentes separadamente. Contabilizar timeouts como resultado, não removê-los dos percentis silenciosamente.
4. Relatar precisão/cobertura por tipo de oportunidade e intervalos de confiança por conversa. Bootstrap deve reamostrar conversas únicas, não as repetições de latência.
5. Estudo com operadores: randomizar ordem das condições, medir tarefas concluídas, esforço, reuso, qualidade e ruído. Reuso sem julgamento de qualidade não é sucesso.
6. Ajustar thresholds apenas no conjunto de calibração. Testar depois no conjunto fechado. Geração seletiva só vence se mantiver a qualidade relevante, e não apenas por fazer menos chamadas.

Arquivos completos: results/evaluation.json e .csv; results/retrieval.json; results/detectors.json. O JSON principal mantém todas as decisões e tempos, incluindo silêncios e falhas.
