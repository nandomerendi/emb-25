# 3. Contratos, ontologia e experiência

## Contrato de entrada

Criar uma sessão com POST /api/sessions. A configuração fica fixa nessa sessão para não misturar condições experimentais. Alterar a política no frontend abre outra sessão.

```json
{
  "approach": "C",
  "generation": "demo",
  "retrieval": "hybrid",
  "posture": "proactive",
  "min_confidence": 0.7,
  "cooldown_seconds": 8,
  "dedup_seconds": 90,
  "expiry_seconds": 45,
  "use_state": true,
  "use_suppression": true
}
```

POST /api/sessions/{id}/events recebe:

```json
{
  "event_id": "evt-0001",
  "sequence": 1,
  "role": "customer",
  "text": "Estou achando a anuidade desse cartão muito cara. Não sei se vale a pena continuar.",
  "request_assist": false
}
```

O servidor exige sequência estritamente crescente; o mesmo event_id/payload retorna um recibo de replay sem repetir a decisão. Mesmo ID com outro payload ou mensagem fora de ordem recebe HTTP 409. O hash de idempotência não guarda o texto original. A transcrição mantida na sessão já passou pelo mascaramento básico. Texto limitado a 3.000 caracteres. Na postura reativa, request_assist=true é o pedido humano explícito.

Resposta em **SSE sobre POST/fetch**, não EventSource GET. Eventos:

| Evento | Contrato | Efeito na interface |
|---|---|---|
| state | event_id, revision, mensagem mascarada, sinais, snapshot | Atualiza conversa e indicadores; retira cards invalidados |
| decision | emit, reason, kind, priority, fingerprint, generate, explanation, revision | Mostra o motivo inicial de intervir ou esperar |
| card | id, revisão, tipo, corpo, fontes, método, expiração, grounding | Mostra ou atualiza a intervenção principal |
| trace | estágios, custo, uso, resultado, decisão final, fonte, total e first_useful | Alimenta painel técnico e auditoria |
| done | event_id, revision | Encerra o processamento desse evento |
| replay | event_id, sessão | Confirma repetição idempotente, sem nova inferência |

A decisão final em trace pode diferir da inicial: fonte ausente, geração obsoleta ou abstenção do modelo. Consumidores devem usar **trace como resultado auditável final**. Há limite de 32 eventos na fila de uma requisição; este fluxo produz menos que isso. Desconexão de UI não equivale a um novo turno: a geração pode terminar e continuar no snapshot. Não há reconexão com replay SSE de cada token; GET da sessão recupera o estado.

## Ontologia mínima

| Dimensão | Exemplos | Origem |
|---|---|---|
| Produto | cartao, conta | Palavra observada ou inferência a partir de assunto inequívoco |
| Assunto | anuidade, beneficios, pix, seguranca, reserva, tarifa | Match textual da ontologia |
| Intenção | duvida, avaliacao, cancelamento, interesse, reclamacao, indefinida | Inferência heurística |
| Objeção | preco | Expressões explícitas |
| Sentimento | positivo, negativo, nao_determinado | Indício lexical; nunca fato psicológico |
| Momento | investigacao, consideracao_permanencia, resolucao | Estado derivado |

O arquivo data/ontology.json contém regras e versão. Cada evidência de match inclui dimensão, valor, texto observado, método, score e tipo observed/inferred. Produto herdado do estado ou derivado do assunto não recebe falsa evidência de citação. “Intenção inferida” não é o mesmo que uma declaração explícita do cliente.

No exemplo inicial: cartão/anuidade/preço são observações; avaliação/consideração de permanência são inferências; existe risco possível de saída sem pedido explícito de cancelamento. **Sentimento pode permanecer não determinado**, pois o exemplo não obriga o sistema a inferir emoção. Isso é uma escolha conservadora.

## Modelo de estado

InteractionState: revision, product, subject, intent, journey, resolved, complaint_open, pending_question, operator_subject, operator_at, recent, sentiment_history, signal_evidence.

- Janela recente: oito falas; sentimento: seis observações com evidência.
- Operador prometer verificar não marca atendimento como resolvido.
- Cliente confirmar resolução limpa a reclamação e invalida cards ativos.
- Mudança de assunto invalida a recomendação antiga e reabre a análise.
- Pergunta pendente é registrada; **não há ainda acompanhamento robusto de múltiplas pendências nem de seu fechamento semântico**. Não fingimos que preencher o campo resolve esse problema.
- Contexto comercial limitado ao que foi dito. Não há posse de produtos, CRM, perfil de investimento ou elegibilidade presumidos.

## Cinco níveis visuais

| Nível | Experiência implementada | Quando aparece | Controle humano |
|---|---|---|---|
| 1. Sinal discreto | Faixa com produto/assunto/intenção e pontos de tendência | Estado muda, mesmo sem card | Evidências inspecionáveis; sem mensagem enviada |
| 2. Conhecimento contextual | Card de documento ou seção de fontes com conteúdo expandível | Há documento no escopo | Operador consulta a fonte e pode dispensar o card |
| 3. Resposta sugerida | Rascunho editável de até 300 caracteres | Pergunta com fonte apropriada | Inserir no composer, revisar e enviar manualmente |
| 4. Orientação | Pergunta de investigação ou próximo passo | Preço, ambiguidade, interesse ou insatisfação | Pode usar, dispensar e avaliar |
| 5. Alerta relevante | Destaque contido para segurança/possível saída | Risco que justifica atenção | Orientação interna; sem envio automático |

O operador vê no máximo uma intervenção principal ativa. O estado permanece visível sem empilhar notificações. Expiração por relógio remove o card; mudança de assunto e condução registrada podem removê-lo antes.

Sentimento usa uma sequência pequena de pontos, acompanhada de texto “ainda sem tendência”, “sem mudança”, “sinais de melhora” ou “sinais de piora”. Não há gráfico animado piscando a cada palavra, escala emocional numérica nem alerta baseado apenas em uma mudança cosmética. Esse indicador é heurístico e aparece como tal.

Feedback por card: útil, não útil, dispensado e inserido no rascunho. “Inserido” mede reuso de rascunho, não prova de envio, qualidade ou impacto. Revisão adicional permite registrar relevância, fundamentação e utilidade. Esses dados são exportáveis e analisáveis por eval/session_metrics.py.

## Auditoria e guardrails

1. Mensagens do cliente e documentos entram como dados, separados das instruções do LLM.
2. Apenas documentos locais aprovados são elegíveis; não existe upload de KB pela interface.
3. Bloqueio lexical simples de algumas instruções adversariais, com decisão auditada. **Não é uma defesa completa contra prompt injection**.
4. Saída estruturada exige texto, emit, ids e citação literal de evidência. Validação checa tamanho, ids permitidos, presença da citação, números não sustentados e alguns padrões proibidos.
5. Formato/citação corretos não comprovam entailment. Uma geração pode citar corretamente e ainda conter extrapolação. Por isso o texto gerado é revisão humana obrigatória, e a produção precisa de avaliação semântica/políticas mais fortes.
6. Não há ferramentas de escrita, transação ou envio real. O botão de envio apenas acrescenta uma fala à conversa sintética.
7. Segredos ficam no backend e não entram no bundle React. O modo live só fica disponível quando modelo e chave estão configurados.
8. API tem opção de token único para laboratório. **Não há autenticação federada, RBAC multiusuário nem autorização por carteira implementados.** Executar em localhost; não expor como serviço compartilhado sem evoluir identidade.
9. Mascaramento é parcial para CPF, email e sequências numéricas. Não substitui DLP; auditoria fica em memória por até uma hora. Dados reais estão fora do escopo.

## Arquivos e separação de responsabilidades

- signals.py: ontologia, normalização, evidência e mascaramento.
- state.py: redução incremental dos eventos.
- opportunity.py: política pura de oportunidade/supressão.
- knowledge.py: recuperação/cache e adaptador opcional semântico.
- generation.py: chamada configurável e validação da saída.
- runtime.py: ciclo de vida, cancelamento, auditoria e feedback.
- api.py: validação HTTP, sessão, SSE, exportação e adaptador inicial /invocations.
- frontend/src: experiência React/TypeScript, parser SSE e telemetria de apresentação.

Toda a lógica de negócio pode ser testada sem rede. Não há dependência do AgentCore para executar o laboratório.
