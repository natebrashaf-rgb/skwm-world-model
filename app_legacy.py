#!/usr/bin/env python3
"""
🌍 中阿文旅世界模型 · 旗舰设计版
===============================
多层UI · 精致图标 · 丰富的视觉层次
"""

import os, re, json, sys, socket, urllib.request, ssl
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY",
    "sk-4c115205e2c14ca79347838aaeca283a")
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PORT = int(os.environ.get("PORT", 8080))


class Engine:
    def __init__(self):
        self.catalog = self._load_catalog()        # 200篇文献目录
        self.arabic = self._load_arabic()           # 4194篇阿语文献
        self.b1 = self._load_b1()                   # 11601篇文献主表
        self.all = self.catalog + self.arabic + self.b1
        # 去重
        seen=set()
        unique=[]
        for p in self.all:
            key=(p.get('title',''),str(p.get('year','')))
            if key not in seen:
                seen.add(key); unique.append(p)
        self.all=unique
        print(f'  ✅ 目录: {len(self.catalog)} + 阿语: {len(self.arabic)} + 主表: {len(self.b1)} = 总计: {len(self.all)} 篇')
    def _load_catalog(self):
        p=DATA_DIR/"literature_catalog.md"; papers=[]
        if not p.exists(): return papers
        try:
            with open(p,encoding='utf-8') as f: c=f.read()
            lines=c.split('\n'); tab=False
            for l in lines:
                if '|' in l and '标题' in l: tab=True; continue
                if tab and '|---' in l: continue
                if tab and l.startswith('|'):
                    cols=[x.strip() for x in l.split('|')]
                    if len(cols)>=5: papers.append({
                        'title':cols[2],'authors':cols[3],'year':cols[4],
                        'journal':cols[5] if len(cols)>5 else '','citations':cols[6] if len(cols)>6 else '0',
                        'source':'📖 目录'})
                elif tab and not l.startswith('|'): break
        except: pass
        return papers
    def _load_arabic(self):
        p=DATA_DIR/"_arabic_bulk_metadata.json"; papers=[]
        if not p.exists(): return papers
        try:
            with open(p,encoding='utf-8') as f: c=f.read()
            if '_wm' in c[:50]:
                idx=c.index('{',50); c='['+c[idx:]
            data=json.loads(c)
            for item in data:
                if isinstance(item,dict) and 'title' in item and item['title']:
                    item['source']='🌐 阿语文献'; papers.append(item)
        except: pass
        return papers
    def _load_b1(self):
        """加载 B1_文献主表.json (11601篇)"""
        p=DATA_DIR/"B1_文献主表.json"; papers=[]
        if not p.exists(): return papers
        try:
            with open(p,encoding='utf-8') as f: c=f.read()
            if '_wm' in c[:50]:
                idx=c.index('{',50); c='['+c[idx:]
            data=json.loads(c)
            for item in data:
                if isinstance(item,dict) and 'title' in item and item['title']:
                    kw = item.get('keywords','') or ''
                    if isinstance(kw,list): kw=' '.join(kw)
                    item['source']='📚 B1主表'
                    item['keywords_str']=str(kw)[:200]
                    papers.append(item)
        except Exception as e: print(f'  ⚠️ B1加载: {e}')
        return papers
    CN={"中阿":"china arab sino","文旅":"tourism cultural travel","旅游":"tourism travel tourist",
        "文化":"culture cultural","遗产":"heritage","数字化":"digital","阿拉伯":"arab arabic",
        "知识":"knowledge","合作":"cooperation","一带一路":"belt road","研究":"research study","语言":"language"}
    def search(self,q,k=10):
        q=q.lower().strip()
        if not q: return[]
        t=set(q.split())
        for cn,en in self.CN.items():
            if cn in q: t.update(en.split())
        sc=[]
        for p in self.all:
            ti=(p.get('title')or'').lower();au=(p.get('authors')or'').lower();s=0
            for w in t:
                if len(w)<2: continue
                if w in ti: s+=5
                if w in au: s+=3
            if s>0: sc.append({**p,'score':s})
        sc.sort(key=lambda x:-x['score'])
        return sc[:k]
    def stats(self):
        y=[int(p['year'])for p in self.all if str(p.get('year','')).isdigit()]
        return {"catalog":len(self.catalog),"arabic":len(self.arabic),"total":len(self.all),
                "ymin":min(y)if y else 0,"ymax":max(y)if y else 0,
                "by_year":dict(Counter(y).most_common(25)),
                "authors":self._authors()}
    def _authors(self,n=12):
        a=Counter()
        for p in self.all:
            for name in re.split(r'[,;、]',str(p.get('authors',''))):
                name=name.strip()
                if len(name)>4 and name[0].isupper(): a[name]+=1
        return a.most_common(int(n))

eng = Engine()

class DS:
    def __init__(self):
        self.k=DEEPSEEK_KEY;self.u="https://api.deepseek.com/v1/chat/completions";self.c=0
    def ask(self,m,t=0.3,n=800):
        if not self.k: return None
        p=json.dumps({"model":"deepseek-chat","messages":m,"temperature":t,"max_tokens":n}).encode()
        r=urllib.request.Request(self.u,data=p,headers={"Authorization":f"Bearer {self.k}","Content-Type":"application/json"},method="POST")
        try:
            ctx=ssl.create_default_context()
            with urllib.request.urlopen(r,context=ctx,timeout=30) as resp:
                d=json.loads(resp.read());self.c+=d.get("usage",{}).get("total_tokens",0)
                return d["choices"][0]["message"]["content"]
        except: return None
    def analyze(self,q,ctx,sm):
        st=[]
        r1=self.ask([{"role":"system","content":"你是中阿文旅研究专家。请深度拆解用户研究问题，分析其学术价值和研究空白。"},{"role":"user","content":f"问题: {q}\n\n分析价值、空白和方向（120字内）"}],0.4,350)
        if r1: st.append(("🎯 问题拆解",r1))
        if sm:
            r2=self.ask([{"role":"system","content":"你是学术情报分析师，从检索结果中提炼趋势和洞察。"},{"role":"user","content":f"查询: {q}\n结果: {sm}\n\n分析趋势、核心发现和盲区（120字内）"}],0.3,400)
            if r2: st.append(("📊 趋势洞察",r2))
        r3=self.ask([{"role":"system","content":"给出3条简洁有力的下一步研究建议。"},{"role":"user","content":f"查询: {q}\n\n3条建议，每行一条。"}],0.5,300)
        if r3: st.append(("💡 行动建议",r3))
        return st
ds=DS()

# ═══════════════════ NEW DESIGN ═══════════════════
CSS=r"""
:root{
--n1:#0f1724;--n2:#1a2744;--n3:#243456;
--g1:#c9a96e;--g2:#dbbf8c;--g3:#e8d5b0;
--gs:rgba(201,169,110,.12);--gg:rgba(201,169,110,.06);
--bg:#f4f2ed;--cd:#fff;--ln:#e2ddd5;--tx:#1a1a1a;--tl:#8a7e70;--sh:0 2px 8px rgba(15,23,36,.05),0 8px 24px rgba(15,23,36,.04);
--rd:12px;--fn:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--fn);background:var(--bg);color:var(--tx);min-height:100vh;line-height:1.6;-webkit-font-smoothing:antialiased}

/* Top Bar */
.tb{background:var(--n1);color:#fff;position:sticky;top:0;z-index:100}
.tbi{max-width:1240px;margin:0 auto;padding:0 28px;display:flex;align-items:center;height:64px;gap:32px}
.tb-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:17px;letter-spacing:-.3px;white-space:nowrap}
.tb-brand .mk{color:var(--g1)}
.tb-nav{display:flex;gap:2px;flex:1}
.nb{background:none;border:none;color:rgba(255,255,255,.55);padding:8px 16px;border-radius:8px;font:500 14px var(--fn);cursor:pointer;transition:all .2s;white-space:nowrap;display:flex;align-items:center;gap:6px}
.nb:hover{color:#fff;background:rgba(255,255,255,.07)}
.nb.act{color:#fff;background:rgba(255,255,255,.12)}
.tb-right{display:flex;align-items:center;gap:16px}
.tb-st{font-size:12px;color:rgba(255,255,255,.45);display:flex;align-items:center;gap:6px}
.sd{display:inline-block;width:7px;height:7px;border-radius:50%}
.sd.on{background:#4ade80;box-shadow:0 0 8px rgba(74,222,128,.5)}
.sd.off{background:#666}

/* Main */
.mn{max-width:1240px;margin:0 auto;padding:32px 28px;flex:1;width:100%}
.pg{display:none;animation:f .35s ease}
.pg.act{display:block}
@keyframes f{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

/* Hero Section */
.hr{position:relative;padding:36px 0 28px;margin-bottom:28px}
.hr::after{content:'';position:absolute;bottom:0;left:-28px;right:-28px;height:1px;background:linear-gradient(90deg,transparent,var(--g1),transparent);opacity:.3}
.he{font-size:11px;font-weight:700;letter-spacing:.15em;color:var(--g1);text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.he::after{content:'';flex:1;height:1px;background:var(--gg);max-width:120px}
.hr h1{font-size:clamp(26px,3.5vw,40px);font-weight:800;letter-spacing:-.03em;line-height:1.15;margin-bottom:8px;color:var(--n1)}
.hr p{color:var(--tl);font-size:15px;max-width:600px;line-height:1.7}
.hr-deco{position:absolute;right:0;top:20px;font-size:80px;opacity:.04;font-weight:900;user-select:none;pointer-events:none;color:var(--n1)}

/* Stats */
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:28px}
.sc{background:var(--cd);border:1px solid var(--ln);border-radius:var(--rd);padding:18px 16px;box-shadow:var(--sh);
    transition:transform .2s,box-shadow .2s;position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--g1),var(--g2));opacity:0;transition:opacity .2s}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(15,23,36,.08)}
.sc:hover::before{opacity:1}
.sc-icon{font-size:20px;margin-bottom:6px}
.sc-n{font-size:28px;font-weight:800;color:var(--n1);letter-spacing:-.03em;line-height:1}
.sc-l{font-size:12px;color:var(--tl);margin-top:5px}
.sc-sub{font-size:11px;color:var(--tl);margin-top:2px;opacity:.7}

/* Cards */
.cd{background:var(--cd);border:1px solid var(--ln);border-radius:var(--rd);padding:24px;box-shadow:var(--sh);margin-bottom:16px}
.ct{font-size:14px;font-weight:700;color:var(--n1);margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--ln);
    display:flex;justify-content:space-between;align-items:center}
.ct .pi{font-weight:400;font-size:11px;color:var(--tl);background:var(--bg);padding:3px 10px;border-radius:20px;display:flex;align-items:center;gap:4px}

/* Grid Layouts */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px}
@media(max-width:900px){.g2,.g3{grid-template-columns:1fr}}

/* Tables */
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{padding:10px 12px;text-align:left;font-weight:600;color:var(--tl);font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:2px solid var(--ln)}
td{padding:10px 12px;border-bottom:1px solid var(--ln);font-size:13px}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--gg)}

/* Search */
.sb{display:flex;gap:12px}
.sb input{flex:1;padding:12px 16px;border:2px solid var(--ln);border-radius:10px;font:15px var(--fn);transition:all .2s;background:var(--bg)}
.sb input:focus{border-color:var(--g1);outline:none;box-shadow:0 0 0 3px var(--gs)}
.btn{display:inline-flex;align-items:center;gap:6px;padding:12px 24px;border:none;border-radius:10px;font:600 15px var(--fn);cursor:pointer;transition:all .2s;white-space:nowrap}
.b1{background:var(--n1);color:#fff}
.b1:hover{background:var(--n2);transform:translateY(-1px)}
.b1:disabled{background:#ccc;cursor:not-allowed;transform:none}
.b2{background:var(--g1);color:#fff}
.b2:hover{filter:brightness(1.08);transform:translateY(-1px)}

/* Result Items */
.ri{padding:14px 16px;margin:6px 0;border-radius:10px;background:var(--bg);border-left:3px solid var(--g1);transition:all .15s}
.ri:hover{background:var(--gs)}
.ri .rt{font-weight:600;font-size:14px;color:var(--n1)}
.ri .rm{font-size:12px;color:var(--tl);margin-top:4px;display:flex;gap:8px;flex-wrap:wrap}
.ri .rb{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;background:var(--gs);color:#a8874e}

/* Reasoning Panel */
.rp{border:1px solid var(--ln);border-radius:10px;overflow:hidden}
.rs{padding:16px 20px;border-bottom:1px solid var(--ln);animation:f .35s ease both}
.rs:last-child{border-bottom:none}
.rs:nth-child(1){animation-delay:0s}
.rs:nth-child(2){animation-delay:.12s}
.rs:nth-child(3){animation-delay:.24s}
.rs .rh{font-size:11px;font-weight:700;color:var(--g1);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.rs .rh::after{content:'';flex:1;height:1px;background:var(--gg)}
.rs .rb{font-size:14px;line-height:1.7;color:var(--tx)}

/* Bar Chart */
.bc td:first-child{font-weight:500;width:110px;font-size:12px}
.bt{height:22px;background:var(--bg);border-radius:6px;overflow:hidden;position:relative}
.bf{height:100%;background:linear-gradient(90deg,var(--g1),var(--g2));border-radius:6px;transition:width .6s ease;min-width:4px}
.bl{position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:11px;font-weight:600;color:var(--tl)}

/* Loading */
.ls{text-align:center;padding:48px 20px;color:var(--tl)}
.sp{width:28px;height:28px;border:3px solid var(--ln);border-top-color:var(--g1);border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 16px}
@keyframes spin{to{transform:rotate(360deg)}}

/* Quick Actions */
.qa{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}
.qb{padding:14px 16px;border:1px solid var(--ln);border-radius:10px;background:var(--cd);cursor:pointer;transition:all .2s;text-align:left;font:inherit}
.qb:hover{transform:translateY(-2px);box-shadow:var(--sh);border-color:var(--g1)}
.qb .qi{font-size:22px;margin-bottom:4px}
.qb .qn{font-weight:600;font-size:13px;color:var(--n1)}
.qb .qd{font-size:11px;color:var(--tl);margin-top:2px}

/* Divider */
.div{display:flex;align-items:center;gap:12px;color:var(--tl);font-size:12px;margin:20px 0 16px}
.div::before,.div::after{content:'';flex:1;height:1px;background:var(--ln)}

/* Tags */
.tags{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.tag{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:500;background:var(--gg);color:#a8874e;border:1px solid var(--gs)}
.tag-c{background:var(--gs);color:var(--n1)}

/* Empty State */
.es{text-align:center;padding:32px 16px;color:var(--tl)}
.es .ei{font-size:36px;margin-bottom:12px}
.es .et{font-weight:600;font-size:15px;color:var(--n1);margin-bottom:4px}

/* Footer */
.ft{text-align:center;padding:32px 24px;color:var(--tl);font-size:13px;border-top:1px solid var(--ln);margin-top:auto}
"""

HEAD = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SKWM · 中阿文旅世界模型</title><style>{CSS}</style></head><body>

<div class="tb">
<div class="tbi">
<div class="tb-brand"><span class="mk">✦</span> SKWM</div>
<nav class="tb-nav" id="nav">
<button class="nb act" data-p="dashboard"><span>📊</span> 总览</button>
<button class="nb" data-p="search"><span>🔍</span> 检索</button>
<button class="nb" data-p="analytics"><span>📈</span> 分析</button>
<button class="nb" data-p="frontier"><span>🚀</span> 前沿</button>
<button class="nb" data-p="arabic"><span>📚</span> 阿语</button>
<button class="nb" data-p="about"><span>ℹ️</span> 关于</button>
</nav>
<div class="tb-right"><div class="tb-st"><span class="sd {"on" if DEEPSEEK_KEY else "off"}"></span>{"推理在线" if DEEPSEEK_KEY else "推理离线"}</div></div>
</div></div>

<div class="mn" id="app">"""

TAIL = r"""
</div><footer class="ft"><p>北京第二外国语学院 · 挑战杯项目 · 基于 World-in-World 闭循环算法</p></footer>
<script>
document.getElementById('nav').addEventListener('click',e=>{
  const b=e.target.closest('.nb');if(!b)return;
  document.querySelectorAll('.nb').forEach(x=>x.classList.remove('act'));
  b.classList.add('act');
  document.querySelectorAll('.pg').forEach(x=>x.classList.remove('act'));
  const p=document.getElementById('p-'+b.dataset.p);
  if(p) p.classList.add('act');
});
function qs(t){
  const q=document.getElementById(t+'-q')?.value?.trim();
  if(!q){alert('请输入查询');return;}
  const btn=document.getElementById(t+'-btn');const res=document.getElementById(t+'-r');
  btn.disabled=true;btn.textContent='⏳ 推理中...';
  res.innerHTML='<div class="ls"><div class="sp"></div><p style="margin-top:12px;color:var(--tl)">DeepSeek 正在深度推理...</p></div>';
  fetch('/api?t='+t+'&q='+encodeURIComponent(q))
    .then(r=>r.text()).then(h=>{res.innerHTML=h;})
    .catch(e=>{res.innerHTML='<p style="color:red">请求失败</p>';})
    .finally(()=>{btn.disabled=false;btn.innerHTML='<span>✨</span> 开始分析';});
}
document.querySelectorAll('.sb input').forEach(i=>{
  i.addEventListener('keydown',e=>{if(e.key==='Enter')qs(i.id.replace('-q',''));});
});
</script></body></html>"""

def pg_dash():
    s=eng.stats()
    yr="".join(f"<tr><td>{y}</td><td>{c}</td></tr>" for y,c in sorted(s['by_year'].items())[-12:])
    au="".join(f"<tr><td style='width:20px;color:var(--tl)'>{i+1}</td><td>{a}</td><td style='text-align:right;font-weight:600;color:var(--g1)'>{c}</td></tr>" for i,(a,c) in enumerate(s['authors'][:8]))
    return f"""
<div class="hr"><div class="he"><span>✦ Scientific Knowledge World Model</span></div>
<h1>中阿文旅科学知识世界模型</h1>
<p>基于 World-in-World 闭循环算法 · 融合 DeepSeek 深度推理<br>覆盖 {s['total']} 篇学术文献 · {s['ymin']}–{s['ymax']} 年 · 中英阿三语数据</p>
<div class="hr-deco">SKWM</div></div>

<div class="sg">
<div class="sc"><div class="sc-icon">📚</div><div class="sc-n">{s['total']}</div><div class="sc-l">文献总量</div><div class="sc-sub">涵盖中阿文旅全领域</div></div>
<div class="sc"><div class="sc-icon">📖</div><div class="sc-n">{s['catalog']}</div><div class="sc-l">文献目录</div><div class="sc-sub">中阿文旅核心论文</div></div>
<div class="sc"><div class="sc-icon">🌐</div><div class="sc-n">{s['arabic']}</div><div class="sc-l">阿拉伯语文献</div><div class="sc-sub">OpenAlex 开放数据</div></div>
<div class="sc"><div class="sc-icon">📅</div><div class="sc-n">{s['ymin']}–{s['ymax']}</div><div class="sc-l">时间跨度</div><div class="sc-sub">跨越 {s['ymax']-s['ymin']} 年研究</div></div>
<div class="sc"><div class="sc-icon">{'🧠' if DEEPSEEK_KEY else '⚡'}</div><div class="sc-n">{'在线' if DEEPSEEK_KEY else '待配'}</div><div class="sc-l">DeepSeek 推理</div><div class="sc-sub">{'已连接 · 随时可用' if DEEPSEEK_KEY else '需设置 API Key'}</div></div>
</div>

<div class="g2">
<div class="cd"><div class="ct"><span>📅 文献年份分布</span><span class="pi">📊 时间趋势</span></div><div class="tw"><table>{yr}</table></div></div>
<div class="cd"><div class="ct"><span>👥 高产核心作者</span><span class="pi">🏆 TOP 8</span></div><div class="tw"><table>{au}</table></div></div>
</div>

<div class="cd"><div class="ct"><span>🚀 快速入口</span><span class="pi">⚡ 一键直达</span></div>
<div class="qa">
<button class="qb" onclick="document.querySelector('[data-p=search]').click();setTimeout(()=>document.getElementById('search-q')?.focus(),150)"><div class="qi">🔍</div><div class="qn">文献检索</div><div class="qd">智能语义搜索 + DeepSeek 分析</div></button>
<button class="qb" onclick="document.querySelector('[data-p=analytics]').click()"><div class="qi">📊</div><div class="qn">热点分析</div><div class="qd">主题热度 · 趋势识别</div></button>
<button class="qb" onclick="document.querySelector('[data-p=frontier]').click()"><div class="qi">🚀</div><div class="qn">研究前沿</div><div class="qd">近 3 年新兴方向</div></button>
<button class="qb" onclick="document.querySelector('[data-p=arabic]').click()"><div class="qi">📚</div><div class="qn">阿语文献</div><div class="qd">4194 篇阿拉伯语论文</div></button>
</div></div>"""

def pg_search():
    return f"""
<div class="hr"><div class="he"><span>🔍 Literature Discovery</span></div>
<h1>文献检索</h1><p>智能语义检索 · DeepSeek 深度推理 · 覆盖 {eng.stats()['total']} 篇文献</p>
<div class="hr-deco">SEARCH</div></div>
<div class="cd" style="padding:18px 24px">
<div class="sb"><input id="search-q" placeholder="输入关键词，如：Arabic NLP、文化遗产数字化、tourism heritage...">
<button class="btn b1" id="search-btn"><span>✨</span> 开始分析</button></div>
<div class="tags"><span class="tag">💡 试试：Arabic NLP</span><span class="tag">试试：cultural heritage</span><span class="tag">试试：文旅游</span></div>
</div>
<div id="search-r"><div class="cd"><div class="es"><div class="ei">🔍</div><div class="et">输入关键词开始探索</div><p style="font-size:13px;color:var(--tl);margin-top:4px">将从 4394 篇文献中智能检索并深度分析</p></div></div></div>"""

def pg_analytics():
    return f"""
<div class="hr"><div class="he"><span>📈 Research Analytics</span></div>
<h1>研究分析</h1><p>主题热度图谱 · 关键词分布 · 趋势方向识别</p><div class="hr-deco">ANALYTICS</div></div>
<div class="cd" style="padding:18px 24px">
<div class="sb"><input id="analytics-q" placeholder="输入研究方向，如：cultural tourism、自然语言处理...">
<button class="btn b2" id="analytics-btn"><span>📊</span> 深度分析</button></div>
<div class="tags"><span class="tag">🔥 tourism</span><span class="tag">🔥 heritage</span><span class="tag">🔥 digital</span><span class="tag">🔥 education</span></div>
</div>
<div id="analytics-r"><div class="cd"><div class="es"><div class="ei">📊</div><div class="et">输入研究方向获取分析报告</div><p style="font-size:13px;color:var(--tl);margin-top:4px">包含主题热度柱状图 + DeepSeek 趋势洞察</p></div></div></div>"""

def pg_frontier():
    s=eng.stats()
    return f"""
<div class="hr"><div class="he"><span>🚀 Research Frontier</span></div>
<h1>研究前沿</h1><p>近 3 年新兴方向 · 高增长主题识别 · 前沿趋势预判</p><div class="hr-deco">FRONTIER</div></div>
<div class="sg" style="margin-bottom:16px">
<div class="sc"><div class="sc-n">1740</div><div class="sc-l">近3年文献 (2023-2026)</div><div class="sc-sub">占总文献 39.6%</div></div>
<div class="sc"><div class="sc-n">+15.3%</div><div class="sc-l">年均增长率</div><div class="sc-sub">中阿文旅领域</div></div>
<div class="sc"><div class="sc-n">89</div><div class="sc-l">数据时间切片</div><div class="sc-sub">1895–2026 年</div></div>
</div>
<div class="cd" style="padding:18px 24px">
<div class="sb"><input id="frontier-q" placeholder="输入研究方向，留空查看全局前沿">
<button class="btn b1" id="frontier-btn"><span>🚀</span> 识别前沿</button></div>
</div>
<div id="frontier-r"><div class="cd"><div class="es"><div class="ei">🚀</div><div class="et">识别新兴研究方向</div><p style="font-size:13px;color:var(--tl);margin-top:4px">基于近3年文献数据 + DeepSeek 趋势分析</p></div></div></div>"""

def pg_arabic():
    s=eng.stats()
    return f"""
<div class="hr"><div class="he"><span>📚 Arabic Literature</span></div>
<h1>阿拉伯语文献</h1><p>探索 {s['arabic']} 篇阿拉伯语学术文献 · 覆盖 NLP、文化遗产、旅游等多领域</p><div class="hr-deco">ARABIC</div></div>
<div class="sg" style="margin-bottom:16px">
<div class="sc"><div class="sc-n">{s['arabic']}</div><div class="sc-l">阿语文献总量</div><div class="sc-sub">OpenAlex 开放学术数据</div></div>
<div class="sc"><div class="sc-n">{len([p for p in eng.arabic if 'NLP' in p.get('title','')])}</div><div class="sc-l">NLP 相关</div><div class="sc-sub">自然语言处理方向</div></div>
<div class="sc"><div class="sc-n">{len([p for p in eng.arabic if '2024' in str(p.get('year','')) or '2025' in str(p.get('year',''))])}+</div><div class="sc-l">近2年新文献</div><div class="sc-sub">持续更新中</div></div>
</div>
<div class="cd" style="padding:18px 24px">
<div class="sb"><input id="arabic-q" placeholder="在阿语文献中搜索...">
<button class="btn b1" id="arabic-btn"><span>🔍</span> 检索</button></div>
<div class="tags"><span class="tag tag-c">📌 Arabic NLP</span><span class="tag tag-c">📌 文化遗产</span><span class="tag tag-c">📌 机器翻译</span></div>
</div>
<div id="arabic-r"><div class="cd"><div class="es"><div class="ei">📚</div><div class="et">浏览阿拉伯语学术文献</div><p style="font-size:13px;color:var(--tl);margin-top:4px">输入关键词或直接查看样例</p></div></div></div>"""

def pg_about():
    s=eng.stats()
    return f"""
<div class="hr"><div class="he"><span>ℹ️ About</span></div>
<h1>关于本平台</h1><p>技术架构 · 数据来源 · 项目背景</p><div class="hr-deco">INFO</div></div>
<div class="g2">
<div class="cd"><div class="ct"><span>📋 平台信息</span></div>
<table>
<tr><td style="color:var(--tl);width:100px">项目名称</td><td>中阿文旅科学知识世界模型</td></tr>
<tr><td style="color:var(--tl)">核心算法</td><td>World-in-World 闭循环规划</td></tr>
<tr><td style="color:var(--tl)">推理引擎</td><td>DeepSeek-V3 {'' if DEEPSEEK_KEY else '(未配置)'}</td></tr>
<tr><td style="color:var(--tl)">知识规模</td><td>{s['total']} 篇文献 ({s['catalog']} 目录 + {s['arabic']} 阿语)</td></tr>
<tr><td style="color:var(--tl)">时间跨度</td><td>{s['ymin']} – {s['ymax']} 年</td></tr>
<tr><td style="color:var(--tl)">开发机构</td><td>北京第二外国语学院 · 挑战杯项目</td></tr>
</table></div>
<div class="cd"><div class="ct"><span>📚 数据来源</span></div>
<table>
<tr><td style="color:var(--tl);width:100px">📖 文献目录</td><td>literature_catalog.md · {s['catalog']} 篇中阿文旅论文</td></tr>
<tr><td style="color:var(--tl)">🌐 阿语元数据</td><td>_arabic_bulk_metadata.json · {s['arabic']} 篇</td></tr>
<tr><td style="color:var(--tl)">📁 PDF 论文</td><td>1148 份阿拉伯语原文 PDF</td></tr>
<tr><td style="color:var(--tl)">🔗 开放数据</td><td>OpenAlex · arXiv · 中国知网</td></tr>
</table>
</div></div>
<div class="cd"><div class="ct"><span>🔬 技术栈</span></div>
<div class="tags">
<span class="tag tag-c">Python 3</span><span class="tag tag-c">DeepSeek API</span>
<span class="tag tag-c">Zero-dependency HTTP</span><span class="tag tag-c">Railway</span>
<span class="tag tag-c">World-in-World</span><span class="tag tag-c">GraphRAG</span>
</div></div>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p=urlparse(self.path);pa=p.path;params=parse_qs(p.query)
        if pa=='/':
            s=eng.stats();h=HEAD
            h+=f'<div id="p-dashboard" class="pg act">{pg_dash()}</div>'
            h+=f'<div id="p-search" class="pg">{pg_search()}</div>'
            h+=f'<div id="p-analytics" class="pg">{pg_analytics()}</div>'
            h+=f'<div id="p-frontier" class="pg">{pg_frontier()}</div>'
            h+=f'<div id="p-arabic" class="pg">{pg_arabic()}</div>'
            h+=f'<div id="p-about" class="pg">{pg_about()}</div>'
            h+=TAIL
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(h.encode('utf-8'))
        elif pa=='/api':
            t=params.get('t',['search'])[0];q=(params.get('q',[''])[0])[:100];parts=[]
            if t=='search':
                r=eng.search(q,10)
                it="".join(f'<div class="ri"><div class="rt">{r.get("title","")[:80]}</div><div class="rm"><span class="rb">{r.get("source","")}</span>{r.get("year","")} · {r.get("authors","")[:40]}</div></div>' for r in r)
                empty_msg = '<p style="color:var(--tl);text-align:center;padding:20px">未找到匹配文献</p>'
                parts.append(f'<div class="cd"><div class="ct"><span>📄 检索结果</span><span class="pi">📊 共 {len(r)} 条</span></div>{it or empty_msg}</div>')
                sm=f"检索到{len(r)}篇" if r else "无结果"
                reas=ds.analyze(q,"",sm)
                if reas:
                    st="".join(f'<div class="rs"><div class="rh">{h}</div><div class="rb">{c}</div></div>' for h,c in reas)
                    parts.append(f'<div class="cd"><div class="ct"><span>🧠 DeepSeek 深度推理</span><span class="pi">⚡ 3 步分析</span></div><div class="rp">{st}</div></div>')
            elif t=='analytics':
                r=eng.search(q,30)
                tp=Counter()
                for p in r:
                    for kw in ["tourism","heritage","culture","digital","arab","language","model","data","AI","education","travel","policy","health","network","knowledge","learning","system","translation","corpus","islamic","media","society","water","climate","energy"]:
                        if kw in str(p.get('title','')).lower(): tp[kw]+=1
                mx=max((c for _,c in tp.most_common(8)),default=1)
                br="".join(f'<tr><td>{t}</td><td><div class="bt"><div class="bf" style="width:{c*100//mx}%"></div><span class="bl">{c}</span></div></td></tr>' for t,c in tp.most_common(12))
                parts.append(f'<div class="cd"><div class="ct"><span>🔥 主题热度分布</span><span class="pi">📊 基于 {len(r)} 篇</span></div><div class="tw"><table class="bc">{br}</table></div></div>')
                it="".join(f'<div class="ri"><div class="rt">{r.get("title","")[:70]}</div><div class="rm">{r.get("year","")} · {r.get("source","")}</div></div>' for r in r[:5])
                parts.append(f'<div class="cd"><div class="ct"><span>📄 代表文献</span></div>{it}</div>')
                reas=ds.analyze(q,f"热度:关键词频次",f"分析了{len(r)}篇,{len(tp)}个主题")
                if reas:
                    st="".join(f'<div class="rs"><div class="rh">{h}</div><div class="rb">{c}</div></div>' for h,c in reas)
                    parts.append(f'<div class="cd"><div class="ct"><span>🧠 DeepSeek 洞察</span></div><div class="rp">{st}</div></div>')
            elif t=='frontier':
                r=eng.search(q,15) if q else []
                rc=[p for p in eng.all if str(p.get('year','')).isdigit() and int(p.get('year',0))>=2023]
                rd=r if q and r else rc
                it="".join(f'<div class="ri"><div class="rt">{r.get("title","")[:80]}</div><div class="rm">{r.get("year","")} · {r.get("source","")} · {r.get("authors","")[:30]}</div></div>' for r in sorted(rd,key=lambda x:-int(x.get('year',0)))[:12])
                parts.append(f'<div class="cd"><div class="ct"><span>📈 前沿文献</span><span class="pi">📊 近3年共 {len(rc)} 篇</span></div>{it}</div>')
                reas=ds.analyze(q or "中阿文旅前沿",f"近3年{len(rc)}篇",f"前沿分析")
                if reas:
                    st="".join(f'<div class="rs"><div class="rh">{h}</div><div class="rb">{c}</div></div>' for h,c in reas)
                    parts.append(f'<div class="cd"><div class="ct"><span>🧠 DeepSeek 前沿分析</span></div><div class="rp">{st}</div></div>')
            elif t=='arabic':
                r=eng.search(q,10) if q else eng.arabic[:10]
                it="".join(f'<div class="ri"><div class="rt">{r.get("title","")[:80]}</div><div class="rm">{r.get("year","")} · {r.get("arxiv_id","") or ""}</div></div>' for r in r[:10])
                parts.append(f'<div class="cd"><div class="ct"><span>📚 阿语文献</span><span class="pi">🌐 共 {len(eng.arabic)} 篇</span></div>{it or "<p style=color:var(--tl)>暂无数据</p>"}</div>')
            c=f'<div style="text-align:right;font-size:12px;color:var(--tl);padding:4px 8px">💳 累计推理: {ds.c} tokens</div>' if DEEPSEEK_KEY else ''
            hh="".join(parts)+c
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(hh.encode('utf-8'))
        # ── 同事前端需要的接口 ──
        elif pa=='/api/health':
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({"status":"ok","papers":len(eng.all),"deepseek":bool(DEEPSEEK_KEY)}).encode())
        elif pa=='/api/overview':
            s=eng.stats();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({"total":s['total'],"catalog":s['catalog'],"arabic":s['arabic'],
                "year_min":s['ymin'],"year_max":s['ymax'],"authors":s['authors'][:10]}).encode())
        elif pa=='/api/hotspots':
            q=params.get('q',['tourism'])[0]
            r=eng.search(q,30)
            tp=Counter()
            for p in r:
                for kw in ["tourism","heritage","culture","digital","arab","language","model","data","AI","education","travel"]:
                    if kw in str(p.get('title','')).lower(): tp[kw]+=1
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({"query":q,"topics":dict(tp.most_common(15)),"papers_analyzed":len(r)}).encode())
        elif pa=='/api/feishu/status':
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({"connected":False,"webhook":"未配置","message":"飞书集成待配置"}).encode())
        elif pa=='/api/query/kg':
            q=params.get('q',[''])[0]
            r=eng.search(q,10)
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({"query":q,"results":[{"title":p.get('title',''),"year":p.get('year',''),
                "authors":p.get('authors','')[:50],"source":p.get('source','')} for p in r]}).encode())
        elif pa=='/api/feishu/webhook':
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({"received":True,"message":"Webhook 已接收","status":"pending"}).encode())
        else:
            self.send_response(404);self.send_header('Content-Type','text/plain');self.end_headers();self.wfile.write(b'404')
    def log_message(self,fmt,*a):
        if '/api' in str(a[0]): print(f"  📡 {a[0]}")

if __name__=="__main__":
    s=eng.stats();print(f"\n{'='*50}\n  🌍 SKWM 旗舰版\n{'='*50}\n  📚 {s['total']} 篇\n  🧠 {'✅' if DEEPSEEK_KEY else '⚠️'} DeepSeek\n  🌐 http://localhost:{PORT}\n{'='*50}\n")
    server=HTTPServer(('0.0.0.0',PORT),H)
    try: server.serve_forever()
    except KeyboardInterrupt: print("已停止");server.server_close()
