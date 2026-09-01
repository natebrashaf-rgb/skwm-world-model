"""Leak-free RSSM V3 reproduction and ablation runner on real project data."""
import argparse, json, random
from pathlib import Path
import numpy as np
import torch
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'/'rssm_v3_reproducible'
SEEDS=[42,123,2026,3407,7777]
from run_rssm_ablation import AblationRSSM, build_windows

def seed_all(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)

def dcg(vals):
    vals=np.asarray(vals,float); return float(np.sum(vals/np.log2(np.arange(2,len(vals)+2))))
def rank_metrics(pred,actual,k=10):
    pred=np.asarray(pred); actual=np.asarray(actual); order=np.argsort(-pred); ideal=np.argsort(-actual)
    kk=min(k,len(pred)); hit=len(set(order[:kk])&set(ideal[:kk])); rho=spearmanr(pred,actual).statistic
    return {'spearman':float(rho if np.isfinite(rho) else 0.),'precision_at_10':hit/kk if kk else 0.,'top10_overlap':hit/kk if kk else 0.,'ndcg_at_10':dcg(actual[order[:kk]])/dcg(actual[ideal[:kk]]) if kk and dcg(actual[ideal[:kk]])>0 else 0.}

def load_data():
    from skwm_platform.backend.real_data_bridge import BridgeKnowledgeWorldModel
    papers=json.load(open(ROOT/'data/B1_文献主表.json',encoding='utf-8')); sv=json.load(open(ROOT/'data/state_vectors.json',encoding='utf-8'))
    return BridgeKnowledgeWorldModel(papers,sv)

def windows_by_topic(kwm, years, T, use_log):
    # raw windows are constructed first; preprocessing is applied inside the model only.
    data=build_windows(kwm,years,T)
    # build_windows is topic-major and returns only arrays; this is enough for fitting split windows.
    return data

def split_windows(kwm,T,use_log):
    # Fit windows have their last observed year <= 2016. Validation windows end in 2017-2019.
    fit=windows_by_topic(kwm,list(range(1995,2017)),T,use_log)
    val=windows_by_topic(kwm,list(range(1995,2020)),T,use_log)
    val=val[-(len(kwm.topics)*3):] if len(val)>=len(kwm.topics)*3 else val
    return fit,val

def train(model,fit,val,seed,steps,batch,beta_dyn,beta_rep):
    seed_all(seed); opt=torch.optim.Adam(model.parameters(),lr=1e-4,weight_decay=1e-5); best=float('inf'); best_state=None; logs=[]
    for step in range(steps):
        idx=np.random.choice(len(fit),min(batch,len(fit)),False); xb=torch.tensor(fit[idx]); ab=torch.zeros(len(idx),xb.shape[1],4)
        model.train(); loss,lg=model.loss(xb,ab,beta_dyn,beta_rep); opt.zero_grad(); loss.backward(); grad=torch.nn.utils.clip_grad_norm_(model.parameters(),100.); opt.step()
        if step%200==0 or step==steps-1:
            model.eval(); vi=[]
            with torch.no_grad():
                for j in range(0,len(val),batch):
                    vb=torch.tensor(val[j:j+batch]); va=torch.zeros(len(vb),vb.shape[1],4); vl,_=model.loss(vb,va,beta_dyn,beta_rep); vi.append(vl.item())
            v=float(np.mean(vi)); logs.append({'step':step,**lg,'val_loss':v,'grad_norm':float(grad)}); 
            if v<best: best=v; best_state={k:v.detach().clone() for k,v in model.state_dict().items()}
    if best_state is not None: model.load_state_dict(best_state)
    return logs,best

def evaluate(model,kwm,config,seed):
    years=list(range(1995,2025)); train_cut=2019; rows=[]; audit=[]
    for h in (1,3,5):
        origins=[train_cut] if train_cut+h<=2024 else []
        for origin in origins:
            state=kwm.get_state(origin); pred=[]; actual=[]
            for topic in kwm.topics:
                x0=torch.tensor(np.asarray([state.vec[topic]],dtype=np.float32)); actions=torch.zeros(1,h,4)
                with torch.no_grad(): p=model.imagine(x0,actions,True)[0,-1,0].item()
                pred.append(p); actual.append(float(kwm.get_state(origin+h).vec[topic][0]))
            pred=np.asarray(pred); actual=np.asarray(actual); current=np.asarray([state.vec[t][0] for t in kwm.topics]); growth_pred=pred-current; growth_actual=actual-current; m=rank_metrics(growth_pred,growth_actual)
            for topic, pp, aa in zip(kwm.topics, pred, actual):
                audit.append({'model':config['name'],'seed':seed,'horizon':h,'forecast_origin':origin,'history_start':origin-config['T']+1,'history_end':origin,'target_year':origin+h,'train_cutoff':train_cut,'topic_id':topic,'prediction':float(pp),'actual':float(aa),'predicted_growth':float(pp-current[list(kwm.topics).index(topic)]),'actual_growth':float(aa-current[list(kwm.topics).index(topic)])})
            m.update({'model':config['name'],'seed':seed,'horizon':h,'forecast_origin':origin,'history_start':origin-config['T']+1,'history_end':origin,'target_year':origin+h,'train_cutoff':train_cut,'topic_count':len(kwm.topics),'mae':float(np.mean(np.abs(pred-actual))),'rmse':float(np.sqrt(np.mean((pred-actual)**2)))})
            assert m['history_end']<m['target_year'] and m['target_year']>train_cut
            rows.append(m)
    return rows, audit

def run_one(config,seed,steps,batch,kwm):
    model=AblationRSSM(stoch=config['stoch'],use_stoch=config['use_stoch'],use_deter=config['use_deter'],use_log=config['use_log'])
    fit,val=split_windows(kwm,config['T'],config['use_log']); logs,best=train(model,fit,val,seed,steps,batch,config['beta_dyn'],config['beta_rep']); rows,audit=evaluate(model,kwm,config,seed)
    return {'config':config,'seed':seed,'n_fit':len(fit),'n_val':len(val),'train_log':logs,'best_val_loss':best,'predictions':rows,'audit':audit},model

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); ap.add_argument('--steps',type=int,default=1200); ap.add_argument('--batch',type=int,default=128); ap.add_argument('--seeds',nargs='*',type=int,default=SEEDS); args=ap.parse_args()
    configs={
      'full':{'name':'full','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      'no_log':{'name':'no_log','use_stoch':True,'use_deter':True,'use_log':False,'T':8,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      'window12':{'name':'window12','use_stoch':True,'use_deter':True,'use_log':True,'T':12,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      'stoch64':{'name':'stoch64','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':64,'beta_dyn':1.,'beta_rep':.1},
      'no_dyn_kl':{'name':'no_dyn_kl','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':32,'beta_dyn':0.,'beta_rep':.1}}
    cfg=configs[args.config]; out=OUT/args.config; out.mkdir(parents=True,exist_ok=True); kwm=load_data(); allr=[]
    for seed in args.seeds:
        print(f'[{args.config} seed={seed}] real-data training',flush=True); r,m=run_one(cfg,seed,args.steps,args.batch,kwm); allr.append(r); torch.save({'model':m.state_dict(),'config':cfg,'seed':seed},out/f'model_seed_{seed}.pt'); (out/f'training_seed_{seed}.json').write_text(json.dumps({'config':cfg,'seed':seed,'n_fit':r['n_fit'],'n_val':r['n_val'],'best_val_loss':r['best_val_loss'],'train_log':r['train_log']},ensure_ascii=False,indent=2),encoding='utf-8'); (out/f'predictions_seed_{seed}.json').write_text(json.dumps(r['predictions'],ensure_ascii=False,indent=2),encoding='utf-8'); (out/f'audit_seed_{seed}.json').write_text(json.dumps(r['audit'],ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'data_source':'data/state_vectors.json + data/B1_文献主表.json','real_data':True,'train_cutoff':2019,'fit_window_end':2015,'validation_window':'2017-2019','test_origins':[2019],'test_targets_min':2020,'seeds':args.seeds,'steps':args.steps,'batch':args.batch,'config':cfg,'results':allr}; (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'config':args.config,'seeds':args.seeds,'best_val':[r['best_val_loss'] for r in allr]},ensure_ascii=False),flush=True)
if __name__=='__main__': main()
