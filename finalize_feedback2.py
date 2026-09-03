import json,hashlib,csv,math
from pathlib import Path
import numpy as np
from scipy.stats import t
from run_rssm_v3_reproducible_corrected import load_data,rank_metrics
ROOT=Path(__file__).resolve().parent; BASE=ROOT/'output'/'rssm_v3_reproducible_corrected'; OUT=BASE/'feedback2'; OUT.mkdir(parents=True,exist_ok=True); seeds=[42,123,2026,3407,7777]; configs=['full','no_log','window12','stoch64','no_dyn_kl']; kwm=load_data(); topics=list(kwm.topics)
def sha(p):
 h=hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()
def ci(v):
 v=np.asarray(v,float); m=float(v.mean()); s=float(v.std(ddof=1)); q=float(t.ppf(.975,len(v)-1)*s/np.sqrt(len(v))); return {'mean':m,'std':s,'ci95_low':m-q,'ci95_high':m+q,'min':float(v.min()),'max':float(v.max())}
def baseline(h,method):
 out={};
 for tpc in topics:
  hist=np.array([float(kwm.get_state(y).vec[tpc][0]) for y in range(1995,2020)]); actual=float(kwm.get_state(2019+h).vec[tpc][0]);
  if method=='last': p=hist[-1]
  elif method=='moving_avg': p=hist[-3:].mean()
  else:
   x=np.arange(len(hist)); a,b=np.polyfit(x,hist,1); p=max(0,b+a*(len(hist)+h-1))
  out[tpc]=(float(p),actual)
 return out
summary={}; hash_rows=[]; all_audit=[]
for c in configs:
 metric_rows=[]
 for s in seeds:
  pred=BASE/c/f'predictions_seed_{s}.json'; audit=BASE/c/f'audit_seed_{s}.json';
  hash_rows.append({'config':c,'seed':s,'prediction_sha256':sha(pred),'checkpoint_sha256':sha(BASE/c/f'model_seed_{s}.pt')})
  a=json.load(open(audit)); all_audit+=a
  for h in (1,3,5):
   x=[r for r in a if r['horizon']==h]; metric_rows.append({'seed':s,'horizon':h,'mae':float(np.mean([abs(r['prediction']-r['actual']) for r in x])),'rmse':float(np.sqrt(np.mean([(r['prediction']-r['actual'])**2 for r in x]))),'spearman':rank_metrics(np.array([r['predicted_growth'] for r in x]),np.array([r['actual_growth'] for r in x]))['spearman']})
 summary[c]={}
 for h in (1,3,5):
  rr=[r for r in metric_rows if r['horizon']==h]; summary[c][f'h{h}']={k:ci([r[k] for r in rr]) for k in ('mae','rmse','spearman')}
# topic-averaged seed error then bootstrap by topic
paired={}
rng=np.random.default_rng(20260904)
for c in configs:
 paired[c]={}
 for h in (1,3,5):
  bytopic={}
  for s in seeds:
   a=json.load(open(BASE/c/f'audit_seed_{s}.json')); by={r['topic_id']:r for r in a if r['horizon']==h}
   for tpc,r in by.items(): bytopic.setdefault(tpc,[]).append(abs(r['prediction']-r['actual']))
  paired[c][f'h{h}']={}
  for m in ('last','moving_avg','linear'):
   b=baseline(h,m); d=np.array([np.mean(bytopic[tpc])-abs(b[tpc][0]-b[tpc][1]) for tpc in topics]); boot=[float(np.mean(d[rng.integers(0,len(d),len(d))])) for _ in range(5000)]
   paired[c][f'h{h}'][m]={'mean_diff':float(d.mean()),'bootstrap_ci95':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],'topic_count':len(d)}
# topic selection and distribution
sv=json.load(open(ROOT/'data/state_vectors.json',encoding='utf-8')); pre=set().union(*(set(sv[str(y)]) for y in sv if y!='_wm' and int(y)<=2019)); all_latest=set(sv[str(max(int(y) for y in sv if y!='_wm'))]);
def stats(ts):
 vals=np.array([float(sv.get('2019',{}).get(x,[0,0,0,0])[0]) for x in ts]); valid=[]
 for x in ts: valid.append(sum(1 for y in sv if y!='_wm' and sv[y].get(x,[0,0,0,0])[0]!=0))
 return {'count':len(ts),'median_heat_2019':float(np.median(vals)),'zero_heat_2019_ratio':float(np.mean(vals==0)),'median_nonzero_years':float(np.median(valid)),'observed_by_2019_ratio':float(np.mean([x in pre for x in ts]))}
topic_report={'selection_rule':'top 100 by 2019 heat among topics observed by 2019','candidate_pre2019_count':len(pre),'latest_topic_count':len(all_latest),'selected':stats(set(topics)),'all_pre2019_candidates':stats(pre),'all_latest_topics':stats(all_latest)}
# h1 top20 case audit
case=[]; y0=2019; y1=2020; cur=np.array([float(kwm.get_state(y0).vec[t][0]) for t in topics]); act=np.array([float(kwm.get_state(y1).vec[t][0]) for t in topics]); growth=act-cur
for s in seeds:
 a=json.load(open(BASE/'full'/f'audit_seed_{s}.json')); by={r['topic_id']:r for r in a if r['horizon']==1}; pg=np.array([by[t]['predicted_growth'] for t in topics]);
 top=lambda z:[topics[i] for i in np.argsort(-z)[:20]]; case.append({'seed':s,'true_top20_growth':top(growth),'rssm_top20_growth':top(pg),'rssm_overlap':len(set(top(growth))&set(top(pg)))})
result={'protocol':{'train_cutoff':2019,'test_targets':{'h1':2020,'h3':2022,'h5':2024},'topic_count':len(topics),'seeds':seeds,'real_data':True},'seed_metrics':summary,'hashes':hash_rows,'topic_averaged_paired_bootstrap':paired,'topic_selection':topic_report,'h1_top20_case_audit':case}
(BASE/'feedback2'/'feedback2_statistics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with open(BASE/'feedback2'/'topic_audit_all.csv','w',newline='',encoding='utf-8') as f:
 fields=list(all_audit[0]); w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_audit)
print(json.dumps({'configs':configs,'hash_rows':len(hash_rows),'audit_rows':len(all_audit),'topic_count':len(topics),'topic_selection':topic_report},ensure_ascii=False,indent=2))
