# 1. Benchmark oficial e padrões reutilizáveis

Pesquisa consultada em 13/10/2026, horário de São Paulo. Esta é uma comparação de capacidades documentadas, **não um teste de desempenho dos produtos**. Não tivemos acesso a tenants dos fornecedores, traces internos, contratos comerciais ou configurações regionais. Disponibilidade varia por edição, canal, idioma e região.

**Legenda:** D = documentado na fonte oficial; H = hipótese de implementação nossa; ND = não determinado nas fontes consultadas. Marketing sobre ganho de produtividade não foi convertido em evidência de arquitetura ou latência.

## Matriz comparativa

| Solução | Leitura contínua e contexto — D | Decisão e controle de sugestões — D | Experiência e conhecimento — D | O que não está comprovado aqui |
|---|---|---|---|---|
| Google Cloud Agent Assist / PGKA | Acompanha conversa; propõe consulta e contexto em pares chave–valor. | Gatilhos configuráveis por mensagem do cliente, mensagem do agente ou fim de enunciado. Consulta principal aciona busca; consultas adicionais podem ficar disponíveis. | Sugestão de consulta e resposta; opção de carregar respostas assincronamente; filtros por metadados da base. [G1, G2] | Número de chamadas LLM, algoritmo de deduplicação, sentimento como gate, cache e p95 ponta a ponta: ND. |
| Genesys Cloud Agent Copilot | Intenção detectada por NLU; regras também podem reagir a início, transferência e fim de conversa. | Threshold configurável; regras por intenção disparam quando muda a intenção ativa, evitando a mesma recomendação consecutiva. Busca fallback pode atuar a cada turno quando nenhuma regra corresponde. [Y1, Y2] | Artigo, resposta pronta, script, checklist e ação de terceiro; possibilidade de restringir quem aciona a regra, cliente ou agente. | Modelo interno, custo por inferência e p95: ND. Não atribuir a supressão das regras ao fallback de conhecimento. |
| NICE CXone Copilot for Agents | Analisa mensagens e transcrição para identificar a questão; mostra mudança de sentimento com justificativa. | Operação automática ou busca solicitada, conforme configuração. Passos usados podem ficar visualmente concluídos. | Respostas de KB com links e filtros; passos de processo; cards customizados; checklist; feedback positivo/negativo. [N1] | Cadência interna de inferência, limiares emocionais, dedup universal e p95: ND. A documentação também oferece envio direto por ação humana; nosso produto exige passar pelo rascunho. |
| Amazon Connect AI Agent Assistance | Documentação atual de Connect Customer descreve NLU/análise conversacional de chamadas, chats, tarefas e emails. | Recomendações automáticas e consulta manual coexistem; prompts e guardrails configuráveis. | Respostas com documentos, orientação em passos, ferramentas e ações integráveis. [A1, A2] | Não comprova nesta pesquisa a política de silêncio, custo interno ou distribuição de latência. AgentCore é runtime distinto do produto Connect. |
| Salesforce Agentforce Service Assistant | Planos dinâmicos acompanham atualizações de caso ou sessão de mensagens. | Etapas se adaptam ao novo contexto; representante revisa e executa ações sugeridas. | Plano de atendimento, chat de apoio, conhecimento, dados do registro, transcrição e instruções. Planos dinâmicos refazem busca das fontes de grounding a cada etapa. [S1] | Não presumir uma única inferência, cache específico ou p95 ≤4 s. O guidance plan estático e o dynamic plan têm comportamentos diferentes. |
| Microsoft Dynamics 365 Contact Center | Documenta sugestões baseadas em dados da conversa e do caso. | Auto prompts e proactive prompts variam por experiência do produto. | Base interna, resumos e assistência de redação; integração visual familiar ao operador. [M1, M2] | Algoritmo de oportunidade, cadência de chamadas e desempenho do serviço: ND. |

## Conclusões que as evidências permitem

1. **Gatilho de processamento e decisão de exibir são contratos diferentes.** A documentação do PGKA torna os eventos de disparo configuráveis e permite separar sugestão de consulta da resposta [G1]. Isso inspira a entrega progressiva do playground, sem afirmar que copiamos seu mecanismo interno.
2. **Existem caminhos úteis sem texto novo de LLM.** Artigo e resposta pronta são ações documentadas na Genesys [Y1]. São referências concretas para a saída determinística.
3. **A experiência deve acompanhar o trabalho já feito.** Passos e orientação adaptativa nas experiências NICE e Salesforce dão uma referência de produto [N1, S1]. Nossa regra temporal de “operador conduzindo” é H, não uma descrição desses fornecedores.
4. **Mesmo contexto pode servir a perguntas explícitas e assistência automática.** Connect documenta as duas formas de uso [A1]. O compartilhamento de código proposto aqui é uma decisão nossa.
5. **Metadados ajudam a buscar no escopo correto.** Google documenta filtros de conhecimento por conversa [G2]. Produto, vigência, público e autorização devem entrar antes da apresentação.
6. **Silêncio precisa de avaliação própria.** Não basta medir qualidade das respostas emitidas. É necessário rotular também oportunidades perdidas e sugestões desnecessárias. Google recomenda golden sets representativos para knowledge assist [G3].

## Hipóteses e diferenciação a testar

| Proposta nossa — H | Benefício esperado | Como refutar |
|---|---|---|
| Prioridade explícita + supressão baseada no estado | Menos interrupção e repetição | Aumento de oportunidades perdidas, especialmente novas dúvidas no mesmo assunto |
| Fonte/template antes da geração | Menor tempo até informação utilizável | Operador não consegue agir com o primeiro conteúdo e espera o texto final |
| Cancelar geração obsoleta e revalidar revisão antes de publicar | Evitar orientação atrasada | Card antigo ainda aparece após mudança de contexto; custos podem continuar no provedor apesar do cancelamento |
| Sentimento discreto, baseado em evidência | Menos ruído visual | Operador ignora alertas importantes ou confunde heurística com fato |
| Rastrear decisão de silêncio e motivo | Auditoria e calibração mais claras | Rótulos não distinguem silêncio correto de omissão |

**Não demonstrado:** liderança de mercado deste protótipo; equivalência funcional com as suítes; ganho de CSAT/TMA; latência de fornecedores; ROI; detector emocional confiável. Não atribuímos BM25, embeddings, classificador pequeno ou um LLM específico ao interior de um produto sem fonte.

## Fontes oficiais

- **G1 — Google, Proactive generative knowledge assist:** https://docs.cloud.google.com/gemini-enterprise-cx/agent-assist/pgka
- **G2 — Google, Knowledge assist filters:** https://docs.cloud.google.com/gemini-enterprise-cx/agent-assist/ka-filters
- **G3 — Google, Best practices:** https://docs.cloud.google.com/gemini-enterprise-cx/agent-assist/pgka-bp
- **Y1 — Genesys, Configure Agent Copilot rules:** https://help.genesys.cloud/articles/configure-genesys-agent-copilot-rules/
- **Y2 — Genesys, Troubleshooting:** https://help.genesys.cloud/articles/agent-copilot-troubleshooting/
- **N1 — NICE, Copilot for Agents workspace:** https://help.nice-incontact.com/content/agent/cxoneagent/enlightencopilotforagentscxa.htm
- **A1 — AWS, Use AI agents for real-time assistance:** https://docs.aws.amazon.com/connect/latest/adminguide/connect-ai-agent.html
- **A2 — AWS, Create AI agents:** https://docs.aws.amazon.com/connect/latest/adminguide/create-ai-agents.html
- **S1 — Salesforce, New Service Assistant Dynamic Experience:** https://trailhead.salesforce.com/content/learn/modules/service-assistant-dynamic-experience-quick-look/get-to-know-new-service-assistant
- **M1 — Microsoft, Copilot feature availability:** https://learn.microsoft.com/en-us/dynamics365/contact-center/use/copilot-feature-availability
- **M2 — Microsoft, Ask a question:** https://learn.microsoft.com/en-us/dynamics365/contact-center/use/use-ask-a-question
- **O1 — OpenAI, Latency optimization:** https://developers.openai.com/api/docs/guides/latency-optimization
- **O2 — OpenAI, Structured outputs:** https://developers.openai.com/api/docs/guides/structured-outputs
- **R1 — AWS, AgentCore HTTP protocol contract:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html
- **R2 — AWS, AgentCore session isolation:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html

As páginas são documentos vivos. As conclusões se limitam à versão consultada; revalidar antes de uma escolha comercial ou implantação.
