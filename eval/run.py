"""Reproducible comparison, no artificial latency. Real LLM calls require --generation openai."""
import argparse,asyncio,json,platform,sys,time,statistics
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from copilot.runtime import Engine
from copilot.models import Config,Message
from copilot.signals import detect

def pct(values):
 if not values:return {'p50':None,'p95':None,'p99':None,'n':0}
 return {**{f'p{p}':round(float(np.percentile(values,p)),4) for p in (50,95,99)},'n':len(values)}
def rate(a,b):return round(a/b,5) if b else 0.
def summarize(rows,approach,split):
 r=[x for x in rows if x['approach']==approach and x['split']==split and x['role']=='customer']
 tp=sum(x['expected'] and x['emitted'] for x in r);fp=sum(not x['expected'] and x['emitted'] for x in r)
 fn=sum(x['expected'] and not x['emitted'] for x in r);tn=sum(not x['expected'] and not x['emitted'] for x in r)
 calls=sum(x['trace']['usage']['calls_started'] for x in r)
 src=[x for x in r if x['expected'] and x['expected_source']]
 costs=[x['trace']['estimated_llm_cost_usd'] for x in r]
 return {'approach':approach,'split':split,'customer_turns':len(r),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
  'precision':rate(tp,tp+fp),'recall':rate(tp,tp+fn),'unnecessary_rate':rate(fp,tp+fp),
  'false_positive_rate':rate(fp,fp+tn),
  'expected_source_coverage':rate(sum(x['expected_source'] in x['card_source_ids'] for x in src),len(src)),
  'backend_ms':pct([x['trace']['total_backend_ms'] for x in r]),
  'first_useful_backend_ms':pct([x['trace']['first_useful_ms'] for x in r if x['trace']['first_useful_ms'] is not None]),
  'generation_ms':pct([x['trace']['stages_ms']['generation'] for x in r if 'generation' in x['trace']['stages_ms']]),
  'browser_presentation_ms':None,'llm_calls':calls,
  'llm_calls_per_customer_message':rate(calls,len(r)),'llm_calls_per_emitted_insight':rate(calls,tp+fp),
  'generation_requests':sum(x['trace']['generation_requested'] for x in r),
  'input_tokens':sum(x['trace']['usage']['input_tokens'] or 0 for x in r) if all(not x['trace']['usage']['calls_started'] or x['trace']['usage']['input_tokens'] is not None for x in r) else None,
  'output_tokens':sum(x['trace']['usage']['output_tokens'] or 0 for x in r) if all(not x['trace']['usage']['calls_started'] or x['trace']['usage']['output_tokens'] is not None for x in r) else None,
  'estimated_llm_cost_usd':sum(costs) if all(v is not None for v in costs) else None,
  'human_grounding_quality':None,'operator_acceptance':None,
  'note':'Decision correctness only. Sources and semantic answer quality must be assessed separately.'}

async def run(args):
 scenarios=json.loads((ROOT/'data/scenarios.json').read_text())
 e=Engine();rows=[];created=0
 if args.generation=='openai' and not e.generator.ready:
  raise SystemExit('OPENAI_API_KEY and OPENAI_MODEL required. No live measurements were run.')
 start=time.perf_counter()
 policies=[('A',Config(approach='A',generation=args.generation)),('B',Config(approach='B',generation=args.generation,use_state=False)),('C',Config(approach='C',generation=args.generation))]
 if args.ablations:
  policies += [('C_no_suppression',Config(approach='C',generation=args.generation,use_suppression=False)),('C_no_state',Config(approach='C',generation=args.generation,use_state=False)),('C_BM25',Config(approach='C',generation=args.generation,retrieval='bm25'))]
 # Rotate ordering between repetitions to reduce fixed-order cache advantage.
 for repeat in range(args.repeats):
  order=policies[repeat%len(policies):]+policies[:repeat%len(policies)]
  for name,config in order:
   for scenario in scenarios:
    s=e.create(config);created+=1
    for index,turn in enumerate(scenario['turns'],1):
     events=await e.collect(s,Message(event_id=f't{index}',sequence=index,role=turn['role'],text=turn['text']))
     tr=next(x['data'] for x in events if x['type']=='trace')
     cards=[x['data'] for x in events if x['type']=='card']
     rows.append({'repeat':repeat,'approach':name,'scenario':scenario['id'],'split':scenario['split'],
                  'turn':index,'role':turn['role'],'text':turn['text'],'expected':turn['expected_intervention'],
                  'expected_source':turn['expected_source'],'forbidden_sources':turn.get('forbidden_sources',[]),'emitted':bool(cards),
                  'card_source_ids':[d['id'] for c in cards[-1:] for d in c['sources']],
                  'trace':tr,'cache_regime':'mixed_warm_in_process','generation':args.generation})
    del e.sessions[s.id]
 summaries=[summarize(rows,p,sp) for p,_ in policies for sp in ('regression','challenge')]
 failures=[{k:x[k] for k in ('approach','scenario','turn','text','expected','emitted','expected_source','card_source_ids','forbidden_sources')}
           for x in rows if x['repeat']==0 and x['role']=='customer' and (x['expected']!=x['emitted'] or (x['expected'] and x['expected_source'] and x['expected_source'] not in x['card_source_ids']) or bool(set(x['forbidden_sources']) & set(x['card_source_ids'])))]
 result={'run_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'generation':args.generation,
         'measurement_note':'Medições reais em processo Python, corpus sintético de 8 documentos; cache misto aquecido; sem rede/DOM. Templates no modo demo; nenhuma latência de LLM simulada.',
         'environment':{'python':platform.python_version(),'platform':platform.platform(),'model':e.generator.model or None},
         'repeats':args.repeats,'scenarios':len(scenarios),'unique_customer_turns':sum(t['role']=='customer' for s in scenarios for t in s['turns']),
         'evaluated_sessions':created,'elapsed_seconds':time.perf_counter()-start,'summaries':summaries,
         'failures_first_repeat':failures,'human_reviews':None,
         'independence_note':'Repeated turns are latency samples, not independent quality evidence. Hand-authored labels; no human-operator study.',
         'cost_note':'LLM-only estimate. Demo has zero API cost, not zero infrastructure cost. Missing prices/usage stay null.',
         'rows':rows}
 output=ROOT/args.output;output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
 # Persist an analysis-ready table, including unsuccessful/silent turns, no cherry-picking.
 import csv
 with output.with_suffix('.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['approach','split','repeat','scenario','turn','role','expected','emitted','reason','backend_ms','first_useful_ms','llm_calls','generation_requested','cache_hit'])
  for x in rows:
   t=x['trace'];w.writerow([x['approach'],x['split'],x['repeat'],x['scenario'],x['turn'],x['role'],x['expected'],x['emitted'],t['decision']['reason'],t['total_backend_ms'],t['first_useful_ms'],t['usage']['calls_started'],t['generation_requested'],(t['retrieval'] or {}).get('cache_hit')])
 for s in summaries:print(f"{s['approach']:18} {s['split']:11} precision={s['precision']:.3f} recall={s['recall']:.3f} p95={s['backend_ms']['p95']:.3f}ms calls={s['llm_calls']}")
 await e.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repeats',type=int,default=10);p.add_argument('--generation',choices=['demo','openai'],default='demo');p.add_argument('--ablations',action='store_true');p.add_argument('--output',default='results/evaluation.json')
 args=p.parse_args()
 if args.repeats<1 or args.repeats>100:raise SystemExit('repeats must be 1..100')
 asyncio.run(run(args))
