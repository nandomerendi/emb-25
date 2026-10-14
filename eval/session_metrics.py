"""Summarize an exported real playground session, preserving missing evidence as null."""
import argparse,json
import numpy as np

def percentiles(v):
 return {f'p{p}':float(np.percentile(v,p)) for p in (50,95,99)} if v else None

def metrics(data):
 cards=data.get('all_cards',data.get('cards',[]));traces=data.get('audit',[])
 feedback=data.get('feedback',[]);reviews=list(data.get('reviews',{}).values())
 presented={x['card_id'] for x in data.get('presentations',[])}
 accepted={x['card_id'] for x in feedback if x['action']=='accepted'}
 useful={x['card_id'] for x in feedback if x['action']=='helpful'}
 dismissed={x['card_id'] for x in feedback if x['action']=='dismissed'}
 calls=sum(t['usage']['calls_started'] for t in traces)
 costs=[t['estimated_llm_cost_usd'] for t in traces]
 return {'messages':len(traces),'unique_insights':len({c['id'] for c in cards}),
  'presented_insights':len(presented),'inserted_into_draft':len(accepted),
  'draft_reuse_rate':len(accepted & presented)/len(presented) if presented else None,
  'helpful_feedback':len(useful),'dismissed':len(dismissed),
  'reviewed_precision':sum(r['relevant'] for r in reviews)/len(reviews) if reviews else None,
  'reviewed_grounding':sum(r['grounded'] for r in reviews)/len(reviews) if reviews else None,
  'reviewed_usefulness':sum(r['useful'] for r in reviews)/len(reviews) if reviews else None,
  'coverage':None,'coverage_note':'Requires separate labels for ALL opportunities, including silent turns.',
  'presentation_ms':percentiles([x['elapsed_ms'] for x in data.get('presentations',[])]),
  'first_useful_backend_ms':percentiles([t['first_useful_ms'] for t in traces if t.get('first_useful_ms') is not None]),
  'total_backend_ms':percentiles([t['total_backend_ms'] for t in traces]),
  'llm_calls':calls,'llm_calls_per_message':calls/len(traces) if traces else None,
  'llm_calls_per_insight':calls/len(cards) if cards else None,
  'estimated_llm_cost_per_session_usd':sum(costs) if all(c is not None for c in costs) else None,
  'note':'Insertion is a reuse proxy, not proof of sending or business outcome. Feedback is opt-in and selection biased.'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('session_json');args=p.parse_args()
 print(json.dumps(metrics(json.load(open(args.session_json))),ensure_ascii=False,indent=2))
