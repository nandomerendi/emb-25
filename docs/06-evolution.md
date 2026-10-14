# 6. Evolução incremental

## Primeiro: ampliar relevância antes de sofisticar a infraestrutura

1. Coletar conversas autorizadas, desidentificadas e rotuladas por operadores. Separar treino, calibração e teste por conversa/assunto/tempo; não por frases repetidas da mesma sessão.
2. Rotular oportunidade, timing, necessidade pendente, ajuda já dada, tipo de card e fontes aceitáveis. Incluir silêncio, contradição, negação, sarcasmo e mudança de foco.
3. Comparar detector lexical, classificador pequeno e embedding. Ativar fallback só em casos de baixa confiança com valor esperado alto. Medir os falsos negativos causados pelo gate.
4. Refinar deduplicação por necessidade, evitando suprimir novas dúvidas no mesmo assunto. A falha já aparece nos desafios do protótipo.
5. Experimentar a UI com operadores; medir aceitação, relevância e tempo de trabalho, além da inferência.

## AWS Bedrock AgentCore

O backend usa FastAPI e está separado do provider do LLM. AgentCore Runtime hospeda a execução; **não é o modelo, nem um substituto automático do estado de interação**. O contrato HTTP oficial exige formato/portas e caminhos específicos; a referência inclui /invocations e /ping e um Dockerfile que pode ser construído para ARM64. [R1]

Este pacote **não foi implantado nem validado no AgentCore**. O adaptador é inicial, não um deployment pronto para produção. Antes da implantação:

- Construir imagem linux/arm64 e validar contrato na região escolhida.
- Colocar um BFF autenticado entre Dynamics/Teams e runtime. Validar identidade real e autorização de atendimento; não confiar em tenant_id ou customer_id enviados livremente pelo browser.
- Mapear atendimento autenticado para runtimeSessionId e sessão de negócio. Idempotência e sequência têm que sobreviver a reconexões.
- Usar estado durável com versão/CAS em DynamoDB ou armazenamento adequado e cache de sessão quando justificado. A memória atual em Python se perde no restart; não usar múltiplos workers com o store atual.
- Considerar o isolamento de sessão do runtime [R2], mas não confundir com retenção durável, autorização da aplicação ou memória empresarial.
- Manter o gateway de eventos e os pequenos detectores fora do runtime generativo se medições mostrarem que invocar o runtime a cada fala custa demais. Alternativa: uma sessão já ativa com processamento local leve. Comparar cold/warm, custo ocioso e concorrência.
- Ajustar /ping para trabalho ativo; já retorna HealthyBusy enquanto há processamento. Validar lifecycle e drain na implantação real.
- Trocar o adaptador de geração por Bedrock Converse se essa for a política corporativa; a interface do gerador permite isso. **Não há adaptador Bedrock de inferência implementado neste pacote.**
- Publicar spans OpenTelemetry para ingestão, classificação, estado, fila, retrieval, geração, validação e apresentação. Propagar event_id/revision e integrar com CloudWatch/Datadog. Traces JSON do MVP não substituem observabilidade distribuída.

## Contexto do cliente e MCPs

Adicionar snapshot mínimo de contexto no começo do atendimento: identificador opaco, produtos relevantes, restrições e timestamp/fonte. Incluir somente atributos necessários à decisão atual, com validade e finalidade. Isso deve ser enriquecimento autorizado, não um prompt gigante com a vida inteira do cliente.

Separar fatos observados, snapshot consultado e inferências. Atualizar o snapshot quando houver sinal de obsolescência; não carregar dado indefinidamente. Antes de oferta/desconto/transação, consultar elegibilidade atual no sistema autorizado.

MCPs entram como ferramentas reutilizáveis do harness: escopos mínimos, contratos tipados, deadline, redaction, idempotência e confirmação humana para escrita. Uma recomendação não é autorização de execução. Uma action não transforma automaticamente a postura proativa em agente autônomo.

## Canais

- Texto: começar com eventos de mensagem finalizada, revision e papéis confiáveis.
- WhatsApp: testar rajadas curtas e mensagens fragmentadas. Debounce adaptativo de dezenas/centenas de milissegundos é hipótese; medir o custo de esperar e o trabalho evitado.
- Voz: distinguir ASR parcial de transcrição final; tratar speaker attribution, revisões e fim de fala. Não gerar uma nova sugestão por fragmento parcial. Medir captura → ASR → decisão → insight, separando custo de inferência. Alvo de 1–2 s exige estudo próprio.
- Teams/Dynamics: a mesma decisão pode ser apresentada por Adaptive Cards ou componentes próprios. A escolha de card deve vir de um contrato tipado/política de UI, não de HTML arbitrário produzido pelo LLM.

## Portões para avançar

- Primeiro piloto: precisão e cobertura acordadas por tipo de risco em um teste independente; nenhum ganho de precisão pode esconder queda excessiva de cobertura.
- Performance: p95 ≤4 s até insight útil sob carga definida, região real, corpus representativo e identidades/guardrails ativos. Separar p95 de primeira fonte e de rascunho final.
- Segurança: avaliação adversarial, isolamento entre clientes, DLP, autenticação, autorização, revisão de KB e red teaming do caminho de geração.
- Operação: nenhum card obsoleto, idempotência após falhas, métricas de fila/timeout/rejeição e rollback de política.
- Produto: sinal de reuso útil e redução de esforço do operador em experimento controlado. Não usar somente taxa de clique ou TMA.

A próxima versão deve priorizar as falhas de cobertura/escopo observadas, e só depois novas ferramentas ou agentes.
