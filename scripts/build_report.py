from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
e=json.loads((R/'results/evaluation.json').read_text());retr=json.loads((R/'results/retrieval.json').read_text());det=json.loads((R/'results/detectors.json').read_text())
def pc(x):return f'{x*100:.1f}%'
def n(x):return 'não medido' if x is None else f'{x:.3f}'
lines=['# 5. Avaliação objetiva — execução local','',f"Execução: {e['run_at_utc']}. Python {e['environment']['python']}. Modo **{e['generation']}**.",'',
 f"Foram executadas {e['evaluated_sessions']} sessões de replay: 23 cenários × seis políticas/ablações × 20 repetições. Há **44 turnos únicos de cliente**, não milhares de exemplos independentes. São 15 cenários de regressão e oito cenários de desafio. As repetições servem para medir tempo, não para aumentar artificialmente evidência de qualidade.",'',
 'O corpus tem oito documentos fictícios em memória. Os tempos abaixo são medidas reais por perf_counter, em processo Python, com cache misto aquecido e sem rede, fila de produção, ASR ou DOM. Não são valores simulados; tampouco representam um SLA corporativo. Os percentis usam interpolação do NumPy. A ordem das políticas gira entre repetições para reduzir vantagem fixa de cache.', '',
 '## Resultados das decisões de intervenção','',
 '| Política | Conjunto | Precisão da decisão | Cobertura | Desnecessárias entre emitidas | Fonte esperada recuperada* | p50 / p95 / p99 backend (ms) |',
 '|---|---|---:|---:|---:|---:|---|']
for s in e['summaries']:
 lines.append(f"| {s['approach']} | {s['split']} | {pc(s['precision'])} | {pc(s['recall'])} | {pc(s['unnecessary_rate'])} | {pc(s['expected_source_coverage'])} | {n(s['backend_ms']['p50'])} / {n(s['backend_ms']['p95'])} / {n(s['backend_ms']['p99'])} |")
lines += ['', '*Cobertura de fonte entre oportunidades que têm uma fonte esperada; não é uma avaliação de entailment. O desafio de cancelamento de compra proíbe a fonte de cancelamento do cartão, em vez de presumir que seja fraude.', '',
 '## Interpretação','',
 '- C remove o excesso de intervenção nos cenários previstos, mas cobre somente **50% das oportunidades do conjunto de desafio**. A pontuação perfeita na regressão é consequência de um corpus simples, construído junto do protótipo; não comprova generalização.',
 '- Desligar a supressão aumenta cobertura no desafio, com mais ruído na regressão. Há uma fronteira precisão/cobertura que precisa ser calibrada com operadores.',
 '- Mesmo quando decide intervir no momento correto, o sistema pode buscar a política errada. “Cancelar uma compra, não meu cartão” ainda pode levar ao documento de cancelamento de cartão. **Essa falha impede recomendar este detector para produção sem melhoria.**',
 '- A e B usam templates no modo demo. Seus números não representam qualidade de um LLM que poderia decidir abster-se ou interpretar melhor o contexto. Não existe vencedor A/B/C de produção demonstrado nesta entrega.',
 '- Zero chamadas LLM significa zero custo de API nesta execução. Não significa custo operacional total zero.',
 '', '## Falhas mantidas visíveis — C', '', '| Cenário | Mensagem | Esperado → observado | Fontes emitidas |', '|---|---|---|---|']
for f in e['failures_first_repeat']:
 if f['approach']=='C':
  lines.append(f"| {f['scenario']} | {f['text']} | {'intervir' if f['expected'] else 'silêncio'} → {'interveio' if f['emitted'] else 'silêncio'} | {', '.join(f['card_source_ids']) or '—'} |")
lines += ['', 'Não foram acrescentadas regras especiais para fazer essas frases de desafio passarem. A próxima versão deve aprender a distinguir objeto do cancelamento, nova necessidade no mesmo assunto e referências implícitas. Durante a verificação corrigimos dois defeitos do fluxo básico: preservação da condução inicial do operador e acionamento do alerta de transação não reconhecida sem ponto de interrogação. Também corrigimos um rótulo de avaliação: pedir explicação da anuidade após esclarecer o produto é uma oportunidade legítima.', '',
 '## Recuperação: BM25 versus híbrido local','',retr['note'],'',
 '| Modo | Cache | Acurácia top-1 | p50 / p95 / p99 (ms) |','|---|---|---:|---|']
for r in retr['results']:
 lines.append(f"| {r['backend']} | {'aquecido misto' if r['cached'] else 'desabilitado por consulta'} | {pc(r['top1_accuracy'])} | {n(r['latency_ms']['p50'])} / {n(r['latency_ms']['p95'])} / {n(r['latency_ms']['p99'])} |")
lines += ['', 'Neste microcorpus, BM25 e o híbrido acertam 8/10 consultas top-1. Sem cache, BM25 é mais rápido. **Não há evidência de ganho de qualidade do híbrido neste conjunto**; o caminho simples merece ser o primeiro controle experimental. Isso não autoriza extrapolar para milhões de chunks ou para hybrid search de 600–1.500 ms em uma infraestrutura remota.', '',
 'O teste sem cache mede computação da consulta sobre índice já carregado, não cold start do processo. Para escala real, separar index initialization, cold/warm retrieval, filtros ACL, tamanho do corpus, top-k, fan-out, fila, rede e reranker. Executar top-k 1/3/5 com as mesmas consultas e fontes relevantes; aumentar ou diminuir top-k só com evidência de fonte suficiente.', '',
 '## Detectores leves: comparação independente','',det['note'],'',
 '| Detector | Macro-F1 de assunto | Taxa unknown | p50 / p95 / p99 (ms) |','|---|---:|---:|---|']
for d in det['results']:
 lines.append(f"| {d['detector']} | {d['macro_f1']:.3f} | {pc(d['abstention_rate'])} | {n(d['latency_ms']['p50'])} / {n(d['latency_ms']['p95'])} / {n(d['latency_ms']['p99'])} |")
lines += ['', 'Há 35 frases sintéticas de treino e 21 frases distintas de teste. Não são exemplos de produção nem um conjunto grande o bastante para escolher definitivamente um detector. O estudo cobre **assunto**, não intenção completa, emoção ou valor de intervenção. TF-IDF por exemplos foi melhor que regex neste conjunto, mas também abstém menos; isso precisa ser confrontado com falsos positivos e dados fora do domínio. O classificador linear não foi ativado automaticamente no runtime. Embeddings semânticos e SLM não foram medidos.', '',
 '## Métricas, definições e campos ausentes','',
 '| Métrica | Definição / implementação | Resultado disponível |','|---|---|---|',
 '| Precisão | TP / (TP + FP), rótulo de oportunidade por turno | Comparação sintética acima |',
 '| Intervenção desnecessária | FP / todas as intervenções emitidas | Acima; distinta de FPR = FP / negativos reais |',
 '| Cobertura | TP / oportunidades rotuladas | Acima, incluindo turnos silenciosos |',
 '| Qualidade/fundamentação | Revisão humana de utilidade e suporte; compatibilidade de fonte é apenas proxy | Campos e UI implementados; avaliação humana não realizada |',
 '| Reuso/aceitação | Cards inseridos no rascunho / cards apresentados | Instrumentado; não medido com operadores |',
 '| Tempo até insight útil | Primeiro card acionável publicado no backend; separadamente double requestAnimationFrame no browser | Backend medido; apresentação no browser sem amostras nesta entrega |',
 '| p50/p95/p99 | Distribuição por política e estágio; população descrita | JSON/CSV e tabela |',
 '| Chamadas LLM | Tentativas iniciadas por mensagem e por insight | Zero reais na execução demo; pedidos potenciais também registrados |',
 '| Tokens | Usage real do Responses API | Não medidos em provedor real |',
 '| Custo estimado | Tokens × preços fornecidos em USD/milhão | Zero de API em demo; live sem preços/usage retorna desconhecido |',
 '| Estado/supressão | Ablações C_no_state e C_no_suppression | Acima |',
 '', 'O frontend mede a partir do envio da mensagem sintética até duas frames após inserir o card, apenas com a página visível e o card presente no DOM. É uma aproximação de apresentação, não uma confirmação de que o operador leu/compreendeu. Nunca misture esses tempos com perf_counter do servidor; os relógios não são comparados diretamente.', '',
 '## Verificação executada','',
 '- 22 testes Python aprovados: estado, isolamento, sequência, idempotência, cancelamento, resolução, privacidade básica, políticas, alerta, recuperação, saída inválida, integração HTTP e contrato do provider com transporte substituído.',
 '- 2 testes do parser SSE aprovados, incluindo UTF-8 dividido entre chunks.',
 '- TypeScript e build Vite aprovados; frontend compilado incluído.',
 '- Um aviso de depreciação na ponte Starlette/httpx durante testes; não houve falha de execução.',
 '- Não executados: inferência OpenAI real, browser QA visual, container build, carga distribuída, embeddings semânticos, ASR, AgentCore ou julgamento humano. Não há valores inventados para preencher essas lacunas.',
 '', '## Próximo experimento reproduzível','',
 '1. Congelar um conjunto independente por conversa e ter dois revisores de domínio rotulando oportunidade, fonte e timing. Resolver divergências sem olhar a política executada.',
 '2. Rodar A/B/C com mesmo modelo, região, corpus e orçamento de saída, registrando token usage, falhas, cancelamentos e cache. Começar com uma repetição real; não extrapolar os tempos demo.',
 '3. Medir condições cold/warm e rajadas concorrentes separadamente. Contabilizar timeouts como resultado, não removê-los dos percentis silenciosamente.',
 '4. Relatar precisão/cobertura por tipo de oportunidade e intervalos de confiança por conversa. Bootstrap deve reamostrar conversas únicas, não as repetições de latência.',
 '5. Estudo com operadores: randomizar ordem das condições, medir tarefas concluídas, esforço, reuso, qualidade e ruído. Reuso sem julgamento de qualidade não é sucesso.',
 '6. Ajustar thresholds apenas no conjunto de calibração. Testar depois no conjunto fechado. Geração seletiva só vence se mantiver a qualidade relevante, e não apenas por fazer menos chamadas.',
 '', 'Arquivos completos: results/evaluation.json e .csv; results/retrieval.json; results/detectors.json. O JSON principal mantém todas as decisões e tempos, incluindo silêncios e falhas.']
(R/'docs/05-evaluation.md').write_text('\n'.join(lines)+'\n')
intro='''# Sinal — copiloto proativo de referência\n\nProtótipo funcional em Python/FastAPI e React/TypeScript, com pesquisa oficial, decisões arquiteturais, experiência do operador e avaliações locais reproduzíveis.\n\n**Resultado central:** o estado e a supressão controlam bem os exemplos previstos, mas o detector lexical cobre só metade das oportunidades nos desafios. O próximo investimento deve ser em compreensão da necessidade e calibração, não em multiplicar agentes.\n\nO pacote inclui frontend compilado, backend, testes, base fictícia, cenários, adaptador OpenAI, scripts de avaliação e dados brutos. Execução local: instalar requirements.lock em Python 3.12 e executar scripts/run_local.sh; abrir http://127.0.0.1:8000.\n\n**Limites da entrega:** nenhuma inferência LLM real, nenhum deploy AgentCore e nenhuma inspeção visual automatizada em navegador foram realizados. As latências apresentadas são medidas locais reais, identificadas por escopo.\n\n'''
contents=[intro]+[(R/'docs'/name).read_text() for name in ['01-research.md','02-architecture.md','03-design.md','05-evaluation.md','06-evolution.md']]
(R.parent/'Relatorio_Sinal.md').write_text('\n\n---\n\n'.join(contents))
print('Report generated:',R.parent/'Relatorio_Sinal.md')
