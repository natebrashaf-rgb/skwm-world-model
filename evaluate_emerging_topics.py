import json, math
from pathlib import Path
import numpy as np
from run_rssm_v3_reproducible_corrected import load_data
ROOT=Path(__file__).resolve().parent; BASE=ROOT/'output'/'rssm_v3_reproducible_corrected'; OUT=BASE/'emerging_topic_task'; OUT.mkdir(parents=True,exist_ok=True)
seeds=[42,123,2026,3407,7777]; configs=['full','no_log','window12','stoch64','no_dyn_kl']
def average_precision(y,s):
 order=np.argsort(-s); y=np.asarray(y)[order]; pos=max(1,int(y.sum())); hits=0; ap=0.
 for i,v in enumerate(y,1):
  if v: hits+=1; ap+=hits/i
 return float(ap/pos)
def ndcg(y,s,k=10):
 order=np.argsort(-s)[:k]; ideal=np.argsort(-y)[:k]
 def dcg(ix): return float(sum(y[i]/math.log2(j+2) for j,i in enumerate(ix)))
 z=dcg(ideal); return dcg(order)/z if z else 0.
def metrics(y,s,k=10):
 order=np.argsort(-s)[:k]; p=int(np.asarray(y)[order].sum()); total=max(1,int(np.asarray(y).sum())); return {'precision_at_10':p/k,'recall_at_10':p/total,'ndcg_at_10':ndcg(y,s,k),'auprc':average_precision(y,s),'positive_count':total}
kwm=load_data(); topics=list(kwm.topics); rows=[]
for c in configs:
 for h in (1,3,5):
  seed_metrics=[]
  for seed in seeds:
   audit=json.load(open(BASE/c/f'audit_seed_{seed}.json')); r=[x for x in audit if x['horizon']==h]; by={x['topic_id']:x for x in r}; cur=np.array([float(kwm.get_state(2019).vec[t][0]) for t in topics]); actual=np.array([by[t]['actual'] for t in topics]); growth=actual-cur; y=(growth>=np.quantile(growth,.9)).astype(int); rss=np.array([by[t]['predicted_growth'] for t in topics]); last=np.zeros_like(rss)
   for method,s in [('rssm',rss),('last',last)]: seed_metrics.append({'config':c,'horizon':h,'seed':seed,'method':method,**metrics(y,s)})
  for method in ('rssm','last'):
   x=[z for z in seed_metrics if z['method']==method]; rows.append({'config':c,'horizon':h,'method':method,'precision_at_10':float(np.mean([z['precision_at_10'] for z in x])),'recall_at_10':float(np.mean([z['recall_at_10'] for z in x])),'ndcg_at_10':float(np.mean([z['ndcg_at_10'] for z in x])),'auprc':float(np.mean([z['auprc'] for z in x])),'positive_count':x[0]['positive_count']})
Path(OUT/'emerging_topic_metrics.json').write_text(json.dumps({'definition':'positive = future growth at or above the 90th percentile among the pre-registered 100 topics','rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False,indent=2))
