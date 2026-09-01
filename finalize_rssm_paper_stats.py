import json, glob, csv, random
from pathlib import Path
import numpy as np
from scipy.stats import t
from run_rssm_v3_reproducible import load_data, AblationRSSM, evaluate
import torch
ROOT=Path(__file__).resolve().parent; BASE=ROOT/'output'/'rssm_v3_reproducible'; kwm=load_data()
configs=['full','no_log','window12','stoch64','no_dyn_kl']; seeds=[42,123,2026,3407,7777]
def ci(v):
 v=np.asarray(v,float); m=float(v.mean()); s=float(v.std(ddof=1)); h=float(t.ppf(.975,len(v)-1)*s/np.sqrt(len(v))) if len(v)>1 else 0.; return {'mean':m,'std':s,'ci95_low':m-h,'ci95_high':m+h}
def base_pred(h,method):
 y=2019; out=[]
 for topic in kwm.topics:
  hist=np.array([float(kwm.get_state(z).vec[topic][0]) for z in range(1995,y+1)]); actual=float(kwm.get_state(y+h).vec[topic][0]);
  if method=='last': p=hist[-1]
  elif method=='moving_avg': p=hist[-3:].mean()
  else:
   x=np.arange(len(hist)); slope,inter=np.polyfit(x,hist,1); p=max(0,inter+slope*(len(hist)+h-1))
  out.append((topic,float(p),actual))
 return out
# full checkpoints were trained under the corrected protocol; regenerate topic audits without retraining.
for seed in seeds:
 p=BASE/'full'/f'model_seed_{seed}.pt'; payload=torch.load(p,map_location='cpu',weights_only=False); cfg=payload['config']; model=AblationRSSM(stoch=cfg['stoch'],use_stoch=cfg['use_stoch'],use_deter=cfg['use_deter'],use_log=cfg['use_log']); model.load_state_dict(payload['model']); model.eval(); rows,audit=evaluate(model,kwm,cfg,seed); (BASE/'full'/f'audit_seed_{seed}.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
# collect metrics and audit manifest
all_audit=[]; summaries={}
for c in configs:
 ss=[]; metric_rows=[]
 for seed in seeds:
  d=json.load(open(BASE/c/f'summary.json')) if (BASE/c/'summary.json').exists() else None
  audit=json.load(open(BASE/c/f'audit_seed_{seed}.json'))
  all_audit += audit
  for h in (1,3,5):
   x=[r for r in audit if r['horizon']==h]; pp=np.array([r['prediction'] for r in x]); aa=np.array([r['actual'] for r in x]); gp=np.array([r['predicted_growth'] for r in x]); ga=np.array([r['actual_growth'] for r in x]);
   from run_rssm_v3_reproducible import rank_metrics
   rm=rank_metrics(gp,ga); metric_rows.append({'seed':seed,'horizon':h,'mae':float(np.mean(np.abs(pp-aa))),'rmse':float(np.sqrt(np.mean((pp-aa)**2))),**rm})
 summaries[c]={}
 for h in (1,3,5):
  rows=[r for r in metric_rows if r['horizon']==h]; summaries[c][f'h{h}']={k:ci([r[k] for r in rows]) for k in ('mae','rmse','spearman','precision_at_10','top10_overlap','ndcg_at_10')}
  summaries[c][f'h{h}']['best_seed']=min(rows,key=lambda x:x['mae'])['seed']; summaries[c][f'h{h}']['worst_seed']=max(rows,key=lambda x:x['mae'])['seed']
# manifest
fields=['model','seed','horizon','forecast_origin','history_start','history_end','target_year','train_cutoff','topic_id','prediction','actual','predicted_growth','actual_growth']
with open(BASE/'topic_audit_all.csv','w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(all_audit)
# paired topic bootstrap: compare seed-specific RSSM against each baseline at same target year.
rng=np.random.default_rng(20260901); paired={}
for c in configs:
 paired[c]={}
 for h in (1,3,5):
  diffs={m:[] for m in ('last','moving_avg','linear')}
  for seed in seeds:
   audit=json.load(open(BASE/c/f'audit_seed_{seed}.json')); ar=[r for r in audit if r['horizon']==h]; rss={r['topic_id']:r for r in ar}
   for method in diffs:
    b={t:(p,a) for t,p,a in base_pred(h,method)}; diffs[method] += [abs(rss[t]['prediction']-b[t][1])-abs(b[t][0]-b[t][1]) for t in rss]
  paired[c][f'h{h}']={}
  for method,d in diffs.items():
   d=np.asarray(d); boots=[]
   for _ in range(2000): boots.append(float(np.mean(d[rng.integers(0,len(d),len(d))])))
   paired[c][f'h{h}'][method]={'mean_diff':float(d.mean()),'bootstrap_ci95':[float(np.quantile(boots,.025)),float(np.quantile(boots,.975))]}
result={'protocol':{'train_cutoff':2019,'fit_window_end':2015,'validation_window':'2017-2019','test_origins':[2019],'target_years':{'h1':2020,'h3':2022,'h5':2024},'topic_count':len(kwm.topics),'real_data':True},'summary':summaries,'paired_bootstrap':paired,'notes':['Five-seed CI is across seeds; bootstrap is exploratory topic-level paired resampling pooled across seed predictions.','P@10 is reported as precision_at_10/top10_overlap; Recall@10 is not claimed because the positive set is fixed at Top-10.']}
(BASE/'paper_level_statistics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'audit_rows':len(all_audit),'configs':configs,'full_seeds':seeds,'output':'paper_level_statistics.json'},ensure_ascii=False))
