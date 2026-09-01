"""Real-data RSSM ablation study for this repository."""
import argparse, json, random
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'/'rssm_ablation'
SEED=42

def seed_all(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s)

def symlog(x): return torch.sign(x)*torch.log1p(torch.abs(x))
def symexp(x): return torch.sign(x)*torch.expm1(torch.abs(x))

class AblationRSSM(nn.Module):
    def __init__(self, x_dim=4, a_dim=4, deter=128, stoch=32, hidden=128, use_stoch=True, use_deter=True, use_log=True):
        super().__init__(); self.x_dim=x_dim; self.a_dim=a_dim; self.deter=deter if use_deter else 1; self.stoch=stoch if use_stoch else 1
        self.use_stoch=use_stoch; self.use_deter=use_deter; self.use_log=use_log; self.hidden=hidden
        self.enc=nn.Sequential(nn.Linear(x_dim,hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU())
        self.cell=nn.GRUCell(self.stoch+a_dim,self.deter)
        self.prior=nn.Sequential(nn.Linear(self.deter,hidden),nn.SiLU(),nn.Linear(hidden,2*self.stoch))
        self.post=nn.Sequential(nn.Linear(self.deter+hidden,hidden),nn.SiLU(),nn.Linear(hidden,2*self.stoch))
        self.dec=nn.Sequential(nn.Linear(self.deter+self.stoch,hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU(),nn.Linear(hidden,x_dim))
    def trans(self,x): return symlog(x) if self.use_log else x
    def inv(self,x): return symexp(x) if self.use_log else x
    def dist(self,p):
        m,s=p.chunk(2,-1); return torch.distributions.Normal(m,F.softplus(s)+0.1)
    def step(self,h,z,a,e=None,det=False):
        h=self.cell(torch.cat([z,a],-1),h) if self.use_deter else h*0
        pr=self.dist(self.prior(h))
        if not self.use_stoch: z=torch.zeros_like(z); return h,z,pr,None
        if e is None: z=pr.mean if det else pr.rsample(); return h,z,pr,None
        po=self.dist(self.post(torch.cat([h,e],-1))); z=po.mean if det else po.rsample(); return h,z,pr,po
    def observe(self,x,a):
        b,t,_=x.shape; h=torch.zeros(b,self.deter,device=x.device); z=torch.zeros(b,self.stoch,device=x.device); hs=[];zs=[];prs=[];pos=[]
        for i in range(t):
            e=self.enc(self.trans(x[:,i])); h,z,pr,po=self.step(h,z,a[:,i],e); hs.append(h);zs.append(z);prs.append(pr);pos.append(po)
        return torch.stack(hs,1),torch.stack(zs,1),prs,pos
    def loss(self,x,a,beta_dyn=1.0,beta_rep=0.1):
        h,z,prs,pos=self.observe(x,a); pred=self.inv(self.dec(torch.cat([h,z],-1))); target=self.trans(x); out=self.trans(pred)
        rec=((out-target)**2).mean(); dyn=rec.new_zeros(()); rep=rec.new_zeros(())
        if self.use_stoch:
            for pr,po in zip(prs,pos):
                k=torch.distributions.kl_divergence(po,pr).sum(-1).mean().clamp_min(1.0); dyn=dyn+k; rep=rep+k
            dyn=dyn/len(prs); rep=rep/len(prs)
        total=rec+beta_dyn*dyn+beta_rep*rep; return total,{'loss':total.item(),'recon':rec.item(),'dyn':dyn.item(),'rep':rep.item()}
    @torch.no_grad()
    def imagine(self,x0,actions,det=True):
        b=x0.shape[0]; h=torch.zeros(b,self.deter); z=torch.zeros(b,self.stoch); e=self.enc(self.trans(x0)); h,z,_,_=self.step(h,z,torch.zeros(b,self.a_dim),e,det); out=[]
        for i in range(actions.shape[1]):
            h,z,_,_=self.step(h,z,actions[:,i],None,det); out.append(self.inv(self.dec(torch.cat([h,z],-1))))
        return torch.stack(out,1) if out else x0.new_empty((b,0,self.x_dim))

def build_windows(kwm,years,T):
    seq=[]
    for topic in kwm.topics:
        vals=[]
        for y in years:
            v=np.asarray(kwm.get_state(y).vec.get(topic,np.zeros(4)),dtype=np.float32)
            vals.append(v)
        for i in range(len(vals)-T): seq.append(np.stack(vals[i:i+T]))
    return np.asarray(seq,dtype=np.float32)

def metric(pred,actual):
    e=np.abs(pred-actual); pg=pred-pred*0+0
    rho=spearmanr(pred,actual).statistic; rho=0 if not np.isfinite(rho) else rho
    k=min(10,len(pred)); ps=set(np.argsort(-pred)[:k]); ats=set(np.argsort(-actual)[:k]); hit=len(ps&ats)
    ideal=np.sort(actual)[::-1][:k]; dcg=np.sum(actual[np.argsort(-pred)[:k]]/np.log2(np.arange(2,k+2))); idcg=np.sum(ideal/np.log2(np.arange(2,k+2)))
    return {'mae':float(e.mean()),'spearman':float(rho),'p_at_10':hit/k,'recall_at_10':hit/k,'ndcg_at_10':float(dcg/idcg if idcg>0 else 0)}

def evaluate(model,kwm,years,h):
    ev=[y for y in years if y+h<=years[-1] and y>=years[0]+8][-5:]; rows=[]
    for y in ev:
        cur=kwm.get_state(y); pred=[]; act=[]
        for t in kwm.topics:
            x=torch.tensor([cur.vec[t]],dtype=torch.float32); a=torch.zeros(1,h,4)
            p=model.imagine(x,a,True)[0,-1,0].item(); pred.append(p); act.append(float(kwm.get_state(y+h).vec[t][0]))
        r=metric(np.array(pred),np.array(act)); r.update({'eval_year':y,'horizon':h,'n_topics':len(pred)}); rows.append(r)
    return rows

def run(cfg,steps,batch):
    seed_all(SEED); years=list(range(1995,2025)); from skwm_platform.backend.real_data_bridge import BridgeKnowledgeWorldModel
    import json as J
    papers=J.load(open(ROOT/'data'/'B1_文献主表.json',encoding='utf-8')); sv=J.load(open(ROOT/'data'/'state_vectors.json',encoding='utf-8')); kwm=BridgeKnowledgeWorldModel(papers,sv)
    x=build_windows(kwm,[y for y in years if y<2020],cfg['T']); model=AblationRSSM(stoch=cfg['stoch'],use_stoch=cfg['use_stoch'],use_deter=cfg['use_deter'],use_log=cfg['use_log']); opt=torch.optim.Adam(model.parameters(),lr=1e-4); logs=[]
    for step in range(steps):
        idx=np.random.choice(len(x),min(batch,len(x)),False); xb=torch.tensor(x[idx]); ab=torch.zeros(len(idx),xb.shape[1],4); loss,lg=model.loss(xb,ab,cfg['beta_dyn'],cfg['beta_rep']); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(),100); opt.step(); logs.append({'step':step,**lg})
    result={'config':cfg,'n_sequences':int(len(x)),'train':{'initial_loss':logs[0]['loss'],'final_loss':logs[-1]['loss'],'best_loss':min(z['loss'] for z in logs),'finite':all(np.isfinite(list(z.values())[1:]).all() if False else np.isfinite(z['loss']) for z in logs),'steps':steps},'metrics':{}}
    for h in (1, 3, 5):
        rr=evaluate(model,kwm,years,h); result['metrics'][f'h{h}']={k:float(np.mean([z[k] for z in rr])) for k in ('mae','spearman','p_at_10','recall_at_10','ndcg_at_10')}; result.setdefault('predictions',[]).extend(rr)
    return model,result,logs

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--steps',type=int,default=600); ap.add_argument('--batch',type=int,default=128); args=ap.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
    configs=[
      {'name':'full','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':32,'beta_dyn':1.0,'beta_rep':0.1},
      {'name':'no_stoch','use_stoch':False,'use_deter':True,'use_log':True,'T':8,'stoch':32,'beta_dyn':0.,'beta_rep':0.},
      {'name':'no_deter','use_stoch':True,'use_deter':False,'use_log':True,'T':8,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      {'name':'no_log','use_stoch':True,'use_deter':True,'use_log':False,'T':8,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      {'name':'window4','use_stoch':True,'use_deter':True,'use_log':True,'T':4,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      {'name':'window12','use_stoch':True,'use_deter':True,'use_log':True,'T':12,'stoch':32,'beta_dyn':1.,'beta_rep':.1},
      {'name':'stoch8','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':8,'beta_dyn':1.,'beta_rep':.1},
      {'name':'stoch64','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':64,'beta_dyn':1.,'beta_rep':.1},
      {'name':'no_dyn_kl','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':32,'beta_dyn':0.,'beta_rep':.1},
      {'name':'no_rep_kl','use_stoch':True,'use_deter':True,'use_log':True,'T':8,'stoch':32,'beta_dyn':1.,'beta_rep':0.},
    ]
    allr=[]
    for cfg in configs:
        print('[run]',cfg['name'],flush=True); model,r,logs=run(cfg,args.steps,args.batch); allr.append(r); (OUT/f"{cfg['name']}_training.json").write_text(json.dumps({'config':cfg,'logs':logs},ensure_ascii=False),encoding='utf-8'); (OUT/f"{cfg['name']}_predictions.json").write_text(json.dumps(r['predictions'],ensure_ascii=False,indent=2),encoding='utf-8'); torch.save({'model':model.state_dict(),'config':cfg},OUT/f"{cfg['name']}.pt"); print('[done]',cfg['name'],r['metrics'],flush=True)
    summary={'real_data':True,'data_source':'data/state_vectors.json + data/B1_文献主表.json','seed':SEED,'steps':args.steps,'batch':args.batch,'results':allr}; (OUT/'ablation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
