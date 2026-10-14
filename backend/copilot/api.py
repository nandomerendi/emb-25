import json, os, secrets, time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .models import Config, Message, Feedback, Presentation, Review
from .runtime import Engine
from .signals import ROOT, ONTOLOGY

engine=Engine()

@asynccontextmanager
async def lifespan(app):
    yield
    await engine.close()

app=FastAPI(title='Sinal • Copiloto proativo',version='0.1.0',lifespan=lifespan)

def auth(authorization: str | None = Header(default=None)):
    expected=os.getenv('COPILOT_API_TOKEN','')
    if expected and not secrets.compare_digest(authorization or '', 'Bearer '+expected):
        raise HTTPException(401,'Autenticação necessária')

def session(sid):
    s=engine.sessions.get(sid)
    if not s: raise HTTPException(404,'Sessão não encontrada')
    if time.monotonic()-s.touched>3600: raise HTTPException(410,'Sessão expirada')
    s.touched=time.monotonic()
    return s

@app.get('/ping')
async def ping():
    busy=any(s.task and not s.task.done() for s in engine.sessions.values())
    return {'status':'HealthyBusy' if busy else 'Healthy'}

@app.get('/api/meta',dependencies=[Depends(auth)])
async def meta():
    return {'name':'Sinal','synthetic_only':True,'llm_ready':engine.generator.ready,
            'model':engine.generator.model or None,'dense_ready':engine.knowledge.encoder is not None,
            'ontology':ONTOLOGY,'knowledge':engine.knowledge.docs,
            'scenarios':json.loads((ROOT/'data/scenarios.json').read_text()),
            'limits':{'session_ttl_seconds':3600,'messages_per_session':300,'retained_turns':8},
            'auth_mode':'single_user_token' if os.getenv('COPILOT_API_TOKEN') else 'localhost_demo'}

@app.post('/api/sessions',dependencies=[Depends(auth)])
async def create(config: Config):
    if config.generation=='openai' and not engine.generator.ready:
        raise HTTPException(422,'Defina OPENAI_API_KEY e OPENAI_MODEL no servidor. Use demo sem credenciais.')
    if config.retrieval=='dense' and engine.knowledge.encoder is None:
        raise HTTPException(422,'Defina um modelo local em EMBEDDING_MODEL_PATH para busca semântica.')
    try: return engine.create(config).public()
    except ValueError as e: raise HTTPException(429,str(e))

@app.get('/api/sessions/{sid}',dependencies=[Depends(auth)])
async def get_session(sid:str): return session(sid).public()

@app.post('/api/sessions/{sid}/events',dependencies=[Depends(auth)])
async def post_event(sid:str,msg:Message):
    try: q=await engine.submit(session(sid),msg)
    except ValueError as e: raise HTTPException(409,str(e))
    async def stream():
        while True:
            item=await q.get()
            yield f"event: {item['type']}\ndata: {json.dumps(item['data'],ensure_ascii=False)}\n\n"
            if item['type']=='done': break
    return StreamingResponse(stream(),media_type='text/event-stream',
                             headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/api/sessions/{sid}/cards/{cid}/feedback',dependencies=[Depends(auth)])
async def feedback(sid:str,cid:str,item:Feedback):
    try: return engine.feedback(session(sid),cid,item)
    except KeyError: raise HTTPException(404,'Card não encontrado')

@app.post('/api/sessions/{sid}/presentation',dependencies=[Depends(auth)])
async def presentation(sid:str,item:Presentation):
    s=session(sid)
    if not any(c['id']==item.card_id and c['event_id']==item.event_id for c in s.cards):
        raise HTTPException(404,'Card/evento não encontrado')
    if not any(p['event_id']==item.event_id for p in s.presentations):
        s.presentations.append({**item.model_dump(),'clock':'browser_performance_now_double_raf'})
    return {'recorded':True}

@app.post('/api/sessions/{sid}/cards/{cid}/review',dependencies=[Depends(auth)])
async def review(sid:str,cid:str,item:Review):
    s=session(sid)
    if not any(c['id']==cid for c in s.cards): raise HTTPException(404,'Card não encontrado')
    s.reviews[cid]=item.model_dump()
    return {'saved':True}

@app.get('/api/sessions/{sid}/export',dependencies=[Depends(auth)])
async def export(sid:str):
    s=session(sid)
    return {**s.public(),'all_cards':s.cards,'measurement_note':'Backend timings are real; browser timings only exist after presentation ACKs.'}

@app.get('/api/evaluation',dependencies=[Depends(auth)])
async def evaluation():
    file=ROOT/'results/evaluation.json'
    return json.loads(file.read_text()) if file.exists() else {'status':'not_run'}

# Minimal synchronous HTTP adapter for a future AgentCore Runtime container.
# Deployment, inbound identity mapping and durable state are intentionally separate.
@app.post('/invocations',dependencies=[Depends(auth)])
async def invocations(payload:dict):
    try:
        if payload.get('operation')=='create': return await create(Config.model_validate(payload.get('config',{})))
        s=session(payload['session_id'])
        events=await engine.collect(s,Message.model_validate(payload['message']))
        return {'events':events,'session_id':s.id}
    except (ValueError,KeyError) as e: raise HTTPException(422,'Contrato de invocação inválido')

dist=ROOT/'frontend/dist'
if dist.exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/')
    async def index(): return FileResponse(dist/'index.html')
