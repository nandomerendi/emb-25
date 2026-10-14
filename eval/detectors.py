"""Optional detector study. Separate training phrases and challenge utterances; no deployment claim."""
import json,sys,time
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'backend'))
from copilot.signals import detect,normalize
from copilot.knowledge import tokens
from collections import Counter
from math import log
train={
 'anuidade':['a anuidade do cartão está alta','quero entender a tarifa anual','pago uma cobrança todo ano pelo cartão','o custo anual do cartão vale a pena','a mensalidade do cartão pesa no bolso'],
 'beneficios':['quais os benefícios do cartão','quero saber as vantagens do cartão','o que meu cartão oferece','cartão virtual e acompanhamento de compras','quais são os recursos oferecidos pelo cartão'],
 'pix':['onde está o comprovante pix','quero o recibo da transferência','consultar o histórico do pix','como encontro comprovante de transferência','preciso da prova do pagamento instantâneo'],
 'seguranca':['não reconheço essa compra','tem uma transação desconhecida','acho que caí num golpe','alguém usou meu cartão sem autorização','uma compra que não fiz apareceu'],
 'reserva':['como guardar dinheiro','quero poupar para emergência','gostaria de conhecer opções para economizar','preciso formar uma reserva','guardar um valor para usar depois'],
 'insatisfacao':['estou insatisfeito com o atendimento','estou irritado com a demora','esse atendimento é péssimo','ninguém resolve meu problema','estou decepcionado com o serviço'],
 'unknown':['bom dia','muito obrigado pela ajuda','só queria agradecer','tudo bem por aí','até mais']}
heldout=[('a anuidade veio cara','anuidade'),('a tarifa anual não compensa','anuidade'),('pago todo mês para manter esse plástico','anuidade'),('quais as vantagens do Aurora','beneficios'),('o que está incluído no cartão','beneficios'),('tem cartão virtual','beneficios'),('cadê o comprovante Pix','pix'),('como vejo o recibo do dinheiro enviado','pix'),('preciso provar aquela transferência','pix'),('não reconheço a compra','seguranca'),('usaram meu cartão sem eu deixar','seguranca'),('acho que roubaram minha conta','seguranca'),('quero guardar dinheiro','reserva'),('como juntar um valor para uma emergência','reserva'),('quero formar meu pé de meia','reserva'),('estou insatisfeito','insatisfacao'),('mais uma vez ninguém me ajuda','insatisfacao'),('excelente serviço, só que não','insatisfacao'),('boa tarde','unknown'),('obrigado','unknown'),('quero saber o horário de abertura','unknown')]
texts=[normalize(t) for v in train.values() for t in v];y=[k for k,v in train.items() for t in v]
vectorizer=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5));X=vectorizer.fit_transform(texts)
clf=LogisticRegression(C=8,max_iter=1000,random_state=17).fit(X,y)
counts=[Counter(tokens(t)) for t in texts];df=Counter(w for c in counts for w in c);avg=sum(sum(c.values()) for c in counts)/len(counts)
def regex(t):return detect(t).get('subject','unknown')
def bm25(t):
 q=tokens(t);scores=[]
 for c in counts:
  length=sum(c.values());score=0
  for w in q:
   tf=c[w];score+=log(1+(len(counts)-df[w]+.5)/(df[w]+.5))*tf*2.5/(tf+1.5*(.25+.75*length/avg))
  scores.append(score)
 return y[int(np.argmax(scores))] if max(scores)>.6 else 'unknown'
def centroid(t):
 scores=(X@vectorizer.transform([normalize(t)]).T).toarray().ravel()
 return y[int(scores.argmax())] if scores.max()>.2 else 'unknown'
def linear(t):
 prob=clf.predict_proba(vectorizer.transform([normalize(t)]))[0]
 return str(clf.classes_[prob.argmax()]) if prob.max()>.35 else 'unknown'
methods={'regex':regex,'bm25_examples':bm25,'char_tfidf_examples':centroid,'linear_classifier':linear}
results=[]
for name,fn in methods.items():
 times=[];pred=[]
 for repeat in range(20):
  for text,gold in heldout:
   start=time.perf_counter();p=fn(text);times.append((time.perf_counter()-start)*1000)
   if repeat==0:pred.append(p)
 gold=[g for t,g in heldout]
 results.append({'detector':name,'macro_f1':float(f1_score(gold,pred,average='macro',zero_division=0)),
                 'abstention_rate':sum(x=='unknown' for x in pred)/len(pred),
                 'latency_ms':{f'p{p}':float(np.percentile(times,p)) for p in (50,95,99)},
                 'predictions':[{'text':t,'gold':g,'prediction':p} for (t,g),p in zip(heldout,pred)]})
(R/'results/detectors.json').write_text(json.dumps({'note':'35 synthetic training examples; 21 separate evaluation phrases; 20 timing repetitions. Only subject classification, not sentiment or complete ontology. Thresholds heuristic, no calibration set. No held-out production data; not evidence to choose a production detector.', 'unexecuted':['semantic embeddings: no local encoder configured','small language model: no credentials/model supplied'], 'results':results},ensure_ascii=False,indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='predictions'} for r in results],indent=2))
