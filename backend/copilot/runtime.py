import asyncio, copy, time, uuid
from dataclasses import asdict
from .models import Config, Message
from .signals import detect, redact
from .state import InteractionState
from .opportunity import decide
from .knowledge import Knowledge
from .generation import Generator, validate_draft, estimate_cost

REASONS = {
 'unsafe_input':'Instrução suspeita: conteúdo isolado, sem geração.',
 'reactive_waiting_request':'Postura reativa: aguardando pedido explícito do operador.',
 'operator_turn':'Fala do operador incorporada ao estado; sem interromper.',
 'resolved':'Resolução reconhecida. Nenhuma ajuda adicional necessária.',
 'commercial_during_complaint':'Reclamação pendente: orientação comercial suprimida.',
 'dismissed':'Recomendação equivalente já dispensada pelo operador.',
 'duplicate':'Já existe recomendação equivalente para esta oportunidade.',
 'operator_handling':'Operador já está conduzindo este assunto.',
 'cooldown':'Janela de respiro ativa para este assunto.',
 'low_confidence':'Evidência insuficiente para interromper.',
 'context_only':'Contexto atualizado, sem necessidade clara de ajuda.',
 'eligible_opportunity':'Há uma oportunidade útil ainda não atendida.',
 'requested':'Ajuda solicitada pelo operador.',
 'obsolete':'Uma nova mensagem tornou este trabalho obsoleto.',
 'no_knowledge':'Nenhuma fonte aprovada encontrada; sem resposta factual.',
 'model_abstained':'O modelo optou por não sugerir uma resposta.',
}

class Session:
    def __init__(self,config):
        self.id=str(uuid.uuid4())
        self.config=config
        self.state=InteractionState()
        self.sequence=0
        self.seen={}
        self.history=[]
        self.cards=[]
        self.audit=[]
        self.feedback=[]
        self.presentations=[]
        self.reviews={}
        self.task=None
        self.lock=asyncio.Lock()
        self.touched=time.monotonic()

    def public(self):
        return {'id':self.id,'config':self.config.model_dump(),'sequence':self.sequence,
                'state':self.state.public(),'cards':[c for c in self.cards if c['active'] and c['expires_at']>time.time()],
                'audit':self.audit[-100:],'feedback':self.feedback,'presentations':self.presentations,
                'reviews':self.reviews}

class Engine:
    def __init__(self,knowledge=None,generator=None):
        self.knowledge=knowledge or Knowledge()
        self.generator=generator or Generator()
        self.sessions={}

    def create(self,config= None):
        now=time.monotonic()
        for key,s in list(self.sessions.items()):
            if now-s.touched>3600 and (not s.task or s.task.done()): del self.sessions[key]
        if len(self.sessions)>=200: raise ValueError('Limite local de sessões atingido.')
        s=Session(config or Config()); self.sessions[s.id]=s
        return s

    async def close(self):
        tasks=[s.task for s in self.sessions.values() if s.task and not s.task.done()]
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await self.generator.close()

    async def submit(self,s,msg):
        import hashlib, json
        digest=hashlib.sha256(json.dumps(msg.model_dump(),sort_keys=True).encode()).hexdigest()
        started=time.perf_counter()
        q=asyncio.Queue(maxsize=32)
        async with s.lock:
            if msg.event_id in s.seen:
                if s.seen[msg.event_id]['digest'] != digest: raise ValueError('event_id reutilizado com payload diferente')
                q.put_nowait({'type':'replay','data':{'event_id':msg.event_id,'session':s.public()}})
                q.put_nowait({'type':'done','data':{'event_id':msg.event_id}})
                return q
            if msg.sequence!=s.sequence+1: raise ValueError(f'Sequência esperada: {s.sequence+1}')
            if s.sequence>=300: raise ValueError('Limite de 300 eventos por sessão; crie outra sessão.')
            if s.task and not s.task.done():
                s.task.cancel()
                await asyncio.gather(s.task,return_exceptions=True)
            s.sequence=msg.sequence
            s.touched=time.monotonic()
            clean=msg.model_copy(update={'text':redact(msg.text)})
            # Do not retain unredacted payloads, including idempotency material.
            s.seen[msg.event_id]={'digest':digest}
            t=time.perf_counter(); sig=detect(clean.text)
            stages={'signals':(time.perf_counter()-t)*1000}
            t=time.perf_counter()
            changed=s.state.update(clean,sig,s.touched,s.config.use_state and s.config.approach!='B')
            stages['state']=(time.perf_counter()-t)*1000
            rev=s.state.revision
            if changed or s.state.resolved or clean.role=='operator':
                for card in s.cards:
                    if card['active'] and (changed or s.state.resolved or s.state.operator_subject==card['subject']):
                        card['active']=False
                        card['withdrawn_reason']='state_changed'
            q.put_nowait({'type':'state','data':{'event_id':msg.event_id,'revision':rev,'message':clean.model_dump(),
                                               'signals':sig,'session':s.public()}})
            s.task=asyncio.create_task(self._process(s,clean,sig,rev,q,started,stages))
        return q

    async def _process(self,s,msg,sig,rev,q,started,stages):
        usage={'calls_started':0,'calls_completed':0,'input_tokens':None,'output_tokens':None}
        trace={'event_id':msg.event_id,'sequence':msg.sequence,'role':msg.role,'revision':rev,
               'approach':s.config.approach,'generation_mode':s.config.generation,
               'stages_ms':stages,'usage':usage,'retrieval':None,'decision':{},
               'first_useful_ms':None,'generation_requested':False,'cards_emitted':0,'status':'completed'}
        try:
            t=time.perf_counter()
            decision=decide(msg,sig,s.state,s.config,s.history,time.monotonic())
            stages['opportunity']=(time.perf_counter()-t)*1000
            trace['decision']={**asdict(decision),'explanation':REASONS.get(decision.reason,decision.reason)}
            q.put_nowait({'type':'decision','data':{**trace['decision'],'revision':rev}})
            if not decision.emit: return
            subject=s.state.subject if s.config.use_state else sig.get('subject')
            product=s.state.product if s.config.use_state else sig.get('product')
            # Explicit cancellation must use cancellation policy, not a price-negotiation article.
            search_subject='cancelamento' if sig['explicit_cancel'] else subject
            query=' '.join(filter(None,[msg.text,search_subject,product]))
            t=time.perf_counter()
            if not search_subject and s.config.approach!='A':
                docs,meta=[],{'cache_hit':False,'backend':'skipped_ambiguous','candidate_count':0}
            else:
                docs,meta=self.knowledge.search(query,search_subject,product,s.config.retrieval)
            stages['retrieval']=(time.perf_counter()-t)*1000
            trace['retrieval']=meta
            trace['source_ids']=[d['id'] for d in docs]
            top=docs[0] if docs else None
            if not top and subject and s.config.approach!='A':
                trace['decision'].update(emit=False,reason='no_knowledge',explanation=REASONS['no_knowledge'])
                return
            if decision.kind=='alert':
                title='Priorize a segurança' if subject=='seguranca' else 'Possível saída • investigar sem pressionar'
                body=top['reply'] if top else 'Acolha o pedido e confirme qual é a necessidade antes de orientar.'
            elif decision.kind=='guidance':
                title='Uma pergunta antes do próximo passo'
                body=top['question'] if top else 'Você pode esclarecer a qual produto e a qual cobrança ou serviço está se referindo?'
            else:
                title='Conhecimento para este momento'
                body=top['reply'] if top else 'Qual ponto você gostaria de esclarecer?'
            card={'id':str(uuid.uuid4()),'event_id':msg.event_id,'revision':rev,'kind':decision.kind,
                  'title':title,'body':body,'subject':subject,'priority':decision.priority,
                  'why':decision.expected_value,'sources':docs,'method':'approved_template' if top else 'clarifying_template',
                  'created_at':time.time(),'expires_at':time.time()+s.config.expiry_seconds,
                  'active':True,'grounding':'approved_template' if top else 'no_factual_claim',
                  'feedback':None}
            t=time.perf_counter()
            # Templates are preapproved in the synthetic corpus and must also obey the short-reply contract.
            if len(card['body'])>300: raise ValueError('Template acima de 300 caracteres')
            stages['guardrail']=(time.perf_counter()-t)*1000
            def publish(update=False):
                if s.state.revision != rev: raise asyncio.CancelledError()
                if not update:
                    for prior in s.cards:
                        if prior['active']: prior['active']=False; prior['withdrawn_reason']='replaced'
                    s.cards.append(card)
                    s.cards=s.cards[-100:]
                    s.history.append({'fingerprint':decision.fingerprint,'subject':subject,'priority':decision.priority,
                                      'at':time.monotonic(),'card_id':card['id']})
                    s.history=s.history[-100:]
                    trace['cards_emitted']=1
                    trace['first_useful_ms']=(time.perf_counter()-started)*1000
                q.put_nowait({'type':'card','data':copy.deepcopy(card)})
            # Baseline A waits for the model; B/C can show an actionable source-backed template first.
            if s.config.approach!='A' or s.config.generation=='demo': publish()
            if decision.generate:
                trace['generation_requested']=True
                if s.config.generation=='demo':
                    trace['generation_result']='template_only_no_llm'
                else:
                    t=time.perf_counter()
                    try:
                        public_state=s.state.public()
                        if s.config.approach=='B' or not s.config.use_state:
                            public_state['recent']=public_state['recent'][-1:]
                        context = {'state':public_state,'task':'suggest_or_abstain'}
                        draft=await self.generator.generate(context,docs,usage)
                        stages['generation']=(time.perf_counter()-t)*1000
                        g=time.perf_counter(); valid,why=validate_draft(draft,docs)
                        stages['output_guardrail']=(time.perf_counter()-g)*1000
                        trace['generation_result']=why
                        if not draft.emit:
                            if s.config.approach=='A':
                                trace['decision'].update(emit=False,reason='model_abstained',explanation=REASONS['model_abstained'])
                        elif valid:
                            card.update(body=draft.text,kind='reply',title='Resposta sugerida',method='llm',
                                        grounding='citation_checked_human_review_required', evidence_quote=draft.evidence_quote,
                                        sources=[d for d in docs if d['id'] in draft.source_ids])
                            publish(update=trace['cards_emitted']>0)
                        elif s.config.approach=='A': publish()
                    except asyncio.CancelledError: raise
                    except Exception as exc:
                        stages['generation']=(time.perf_counter()-t)*1000
                        trace['generation_result']='fallback_'+type(exc).__name__
                        # Do not log upstream payloads, credentials, or exception text.
                        if s.config.approach=='A': publish()
            elif s.config.approach=='A' and not trace['cards_emitted']: publish()
        except asyncio.CancelledError:
            trace['status']='cancelled'
            trace['decision'].update(emit=False,reason='obsolete',explanation=REASONS['obsolete'])
            if 'generation' not in stages and usage['calls_started']:
                stages['generation_cancelled_elapsed']=(time.perf_counter()-t)*1000
        except Exception as exc:
            trace['status']='error'
            trace['error']=type(exc).__name__
        finally:
            trace['total_backend_ms']=(time.perf_counter()-started)*1000
            trace['estimated_llm_cost_usd']=estimate_cost(usage)
            trace['cost_scope']='LLM only; infrastructure and cancelled unknown usage excluded'
            s.audit.append(copy.deepcopy(trace)); s.audit=s.audit[-300:]
            q.put_nowait({'type':'trace','data':copy.deepcopy(trace)})
            q.put_nowait({'type':'done','data':{'event_id':msg.event_id,'revision':rev}})

    async def collect(self,s,msg):
        q=await self.submit(s,msg); events=[]
        while True:
            item=await q.get(); events.append(item)
            if item['type']=='done': return events

    def feedback(self,s,card_id,feedback):
        card=next((c for c in s.cards if c['id']==card_id),None)
        if not card: raise KeyError(card_id)
        entry={'card_id':card_id,**feedback.model_dump(),'at':time.time()}
        s.feedback.append(entry); s.feedback=s.feedback[-300:]
        card['feedback']=feedback.action
        if feedback.action=='dismissed':
            card['active']=False
            for h in s.history:
                if h['card_id']==card_id: h['dismissed']=True
        return entry
