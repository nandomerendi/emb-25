"""Small-corpus retrieval microbenchmark. Deliberately includes held-out paraphrases."""
import json,sys,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'backend'))
from copilot.knowledge import Knowledge
queries=[('tarifa anual muito cara','KB-001'),('vantagens do cartão','KB-002'),('quero encerrar cartão','KB-003'),('comprovante de transferência Pix','KB-004'),('compra desconhecida golpe','KB-005'),('estou decepcionado','KB-006'),('poupar para uma emergência','KB-007'),('cesta do pacote da conta','KB-008'),('esse plástico pesa no bolso','KB-001'),('onde consulto o recibo do dinheiro enviado','KB-004')]
k=Knowledge();out=[]
for mode in ['bm25','hybrid']+(['dense'] if k.encoder else []):
 for cached in (False,True):
  times=[];correct=[];ranked=[]
  for rep in range(30):
   for query,gold in queries:
    if not cached:k.cache.clear()
    t=time.perf_counter();docs,meta=k.search(query,mode=mode);times.append((time.perf_counter()-t)*1000)
    correct.append(bool(docs and docs[0]['id']==gold))
    if rep==0:ranked.append({'query':query,'expected':gold,'top1':docs[0]['id'] if docs else None,'top3':[d['id'] for d in docs]})
  out.append({'mode':mode,'cached':cached,'backend':k.backend(mode),'top1_accuracy':sum(correct)/len(correct),'queries':ranked,
              'latency_ms':{f'p{p}':float(np.percentile(times,p)) for p in (50,95,99)}})
result={'note':'10 unique synthetic queries repeated 30 times. Tiny local in-memory corpus, no network, no embeddings unless a local encoder is configured. No claims about enterprise-scale hybrid search.', 'results':out}
(R/'results/retrieval.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps([{k:v for k,v in x.items() if k!='queries'} for x in out],indent=2))
