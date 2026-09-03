import json
from pathlib import Path
import numpy as np
from run_rssm_v3_reproducible import load_data
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'output'/'rssm_v3_reproducible'/'h1_top20_audit'; OUT.mkdir(parents=True,exist_ok=True)
kwm=load_data(); topics=list(kwm.topics); y0=2019; y1=2020
current=np.array([float(kwm.get_state(y0).vec[t][0]) for t in topics]); actual=np.array([float(kwm.get_state(y1).vec[t][0]) for t in topics]); growth=actual-current
rows=[]
for seed in [42,123,2026,3407,7777]:
 audit=json.load(open(ROOT/'output/rssm_v3_reproducible/full'/f'audit_seed_{seed}.json'))
 r=[x for x in audit if x['horizon']==1][0:len(topics)]
 by={x['topic_id']:x for x in r}; pred=np.array([by[t]['prediction'] for t in topics]); pg=pred-current
 def top(vals): return [topics[i] for i in np.argsort(-vals)[:20]]
 rows.append({'seed':seed,'true_top20_by_growth':top(growth),'rssm_top20_by_growth':top(pg),'last_top20_by_growth':top(np.zeros_like(growth)),'true_top20_by_level':top(actual),'rssm_top20_by_level':top(pred),'last_top20_by_level':top(current),'rssm_overlap_growth':len(set(top(pg))&set(top(growth))),'last_overlap_growth':len(set(top(np.zeros_like(growth)))&set(top(growth)))})
 details=[]
 for i in np.argsort(-growth)[:20]: details.append({'topic_id':topics[i],'current_2019':float(current[i]),'actual_2020':float(actual[i]),'actual_growth':float(growth[i]),'rssm_prediction_by_seed':{str(s):float(next(x for x in json.load(open(ROOT/'output/rssm_v3_reproducible/full'/f'audit_seed_{s}.json')) if x['horizon']==1 and x['topic_id']==topics[i])['prediction']) for s in [42,123,2026,3407,7777]},'last_prediction':float(current[i])})
Path(OUT/'summary.json').write_text(json.dumps({'topic_count':len(topics),'forecast_origin':2019,'target_year':2020,'cases':rows,'true_growth_top20_details':details},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False,indent=2))
print('topics',len(topics),'unique',len(set(topics)))
