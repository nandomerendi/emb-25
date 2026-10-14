# Sinal — copiloto proativo para atendimento humano

Protótipo local funcional: **FastAPI + React/TypeScript**, SSE, estado incremental, motor de oportunidades, conhecimento fictício, geração opcional via OpenAI e avaliação A/B/C. Nenhuma mensagem é enviada a clientes reais. Sem credenciais, funciona com fontes e templates aprovados; esse modo não simula latência ou inteligência de um LLM.

## Rodar em poucos passos

Pré-requisito: Python 3.12. O frontend compilado está incluído; **Node não é necessário para experimentar o pacote entregue**.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
bash scripts/run_local.sh
```

Abra http://127.0.0.1:8000 — documentação da API em http://127.0.0.1:8000/docs.

No Windows PowerShell, ative com `.venv\Scripts\Activate.ps1` e execute:

```powershell
python -m uvicorn copilot.api:app --app-dir backend --host 127.0.0.1 --port 8000
```

Use um único worker: o store do MVP é em memória. Reiniciar o processo apaga sessões; exporte o JSON antes de encerrar. Dependências precisam ser instaladas uma vez com acesso à rede. Depois disso, o modo demo não precisa de serviços externos.

## Experimentar

1. Escolha **Vale a pena continuar?** na lateral e avance em **Iniciar / Próxima fala**.
2. Observe preço/anuidade e o alerta de possível saída. Abra a fonte.
3. Avance para a fala do operador: o card perde a utilidade e pode ser retirado.
4. Em **Repetição**, veja o motivo `duplicate` na trilha.
5. Em **Mudança de assunto**, confira a troca de fonte e a invalidação do card anterior.
6. Escreva manualmente como cliente ou operador. Uma nova mensagem durante geração cancela o trabalho pendente.
7. Edite uma resposta sugerida, clique **Inserir no rascunho** e só envie se quiser. Nenhuma inserção envia a mensagem.
8. Compare A, B e C; alterar a política inicia uma sessão limpa. O rótulo **SEM LLM** fica explícito.
9. Mude para postura reativa e use **Pedir ajuda**. O conhecimento e o gerador são os mesmos.
10. Exporte a sessão para analisar apresentações, feedback e revisões.

A aba Experimentos mostra os resultados salvos em results/evaluation.json. Os 15 cenários operacionais aparecem na lateral; outros oito cenários de desafio são executados pelo avaliador e estão em data/scenarios.json.

## Habilitar OpenAI

Use variáveis de ambiente no mesmo terminal em que iniciará o servidor. O arquivo .env.example é uma referência, **não é carregado automaticamente**.

```bash
export OPENAI_API_KEY='sua-chave'
export OPENAI_MODEL='modelo-com-suporte-a-Responses-e-Structured-Outputs'
bash scripts/run_local.sh
```

Defina um modelo disponível na sua conta. Não presumimos modelo mais rápido nem preços. A API usa Responses, JSON Schema, store=false e uma tentativa sem retry por geração. OPENAI_BASE_URL permite endpoint compatível com **Responses**; não basta suportar apenas Chat Completions.

Opções: LLM_TIMEOUT_SECONDS (default 3.2), LLM_MAX_CONCURRENCY (default 4), LLM_INPUT_USD_PER_MILLION e LLM_OUTPUT_USD_PER_MILLION. Sem preço ou uso conhecido, custo fica desconhecido; não vira zero. O orçamento curto pode provocar timeout/incomplete em modelos de raciocínio; o fallback preserva a fonte/template.

Nunca coloque a chave no frontend. O modo live foi testado com transporte HTTP substituído em teste; **não houve inferência OpenAI real nesta entrega**.

## Desenvolver o frontend

Node 24 foi usado nesta entrega. Para o build, Vite requer versão compatível; os testes que importam TypeScript diretamente usam o suporte do Node 24.

```bash
cd frontend
npm ci
npm run dev
```

Vite encaminha /api para o backend em 127.0.0.1:8000. Após alterações:

```bash
npm run build
npm test
```

Reinicie o backend para servir o novo dist. O build usa fontes do sistema e ícones empacotados; não depende de CDNs.

## Testes e avaliações reproduzíveis

Na raiz do projeto, com o ambiente Python ativo:

```bash
python -m pytest -q
python eval/run.py --repeats 20 --ablations
python eval/retrieval.py
python eval/detectors.py
python eval/session_metrics.py caminho/para/sinal-sessao.json
```

Para um estudo real com LLM, configure as credenciais e execute conscientemente:

```bash
python eval/run.py --generation openai --repeats 1 --output results/live-evaluation.json
```

Esse comando faz chamadas reais faturáveis. Comece com uma repetição. Os resultados demo fornecidos não predizem qualidade, tokens ou latência do modelo. Alvos experimentais: caminho determinístico abaixo de 500 ms e p95 até 4 s no caminho com geração, **medidos até informação útil na tela, em infraestrutura representativa**.

## Busca semântica opcional

Default: BM25 + TF-IDF de caracteres, com RRF. Isso é híbrido lexical/morfológico, não embeddings semânticos. Para usar embeddings, instale sentence-transformers e aponte EMBEDDING_MODEL_PATH para pesos já disponíveis localmente. Não há download implícito. O backend permite retrieval=dense; o modo hybrid troca o componente vetorial pelo encoder. Essa opção não foi executada na avaliação entregue.

## Segurança e limites

- Use somente dados sintéticos. A aplicação serve em localhost por padrão.
- COPILOT_API_TOKEN ativa token único no backend e um campo de autenticação na UI. Isso não substitui SSO/RBAC/multitenancy.
- Mascaramento parcial, isolamento em memória por sessão, fonte aprovada, limite de eventos, schema e guardrails de saída implementados.
- A validação de citação não prova que toda afirmação está sustentada. Prompt injection continua exigindo defesa em profundidade.
- O motor lexical erra negações de escopo, ironia, paráfrases e novas perguntas no mesmo assunto. Os desafios preservam esses erros.
- Não há ASR/voz, MCP, contexto transacional de cliente, persistência distribuída ou deploy AWS.
- O build React e os testes de transporte/API passaram. **Não houve inspeção visual/interação em navegador automatizado neste ambiente**. Telemetria DOM existe para uso local; nenhuma medição de apresentação foi fabricada.

## Docker e evolução AWS

```bash
docker build -t sinal-copilot .
docker run --rm -p 127.0.0.1:8000:8080 sinal-copilot
```

Dockerfile incluído, mas build de container não executado nesta sessão. A construção ARM64 e a configuração de identidade/state-store são passos posteriores para AgentCore. /invocations e /ping são um adaptador HTTP inicial; veja docs/06-evolution.md antes de implantar.

## Mapa do projeto

```text
backend/copilot/     sinais, estado, motor, retrieval, geração, runtime e API
backend/tests/       invariantes de contexto, segurança, geração e HTTP
frontend/src/        playground React, apresentação e parser SSE
frontend/dist/       build pronto para servir pelo FastAPI
frontend/tests/      testes do transporte incremental
 data/              ontologia, oito documentos e 23 cenários sintéticos
 eval/              comparação A/B/C, ablações, retrieval, detectores e feedback
 results/           dados reais das execuções locais, JSON e CSV
 docs/              benchmark, decisões, contratos, avaliação e evolução
 scripts/           execução local e geração dos cenários
```

Leia docs/01-research.md → docs/02-architecture.md → docs/03-design.md → docs/05-evaluation.md → docs/06-evolution.md. As referências oficiais estão no benchmark. Os relatórios distinguem capacidades documentadas, hipóteses e medições do protótipo.
