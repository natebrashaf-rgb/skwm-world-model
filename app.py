#!/usr/bin/env python3
"""
🌍 中阿文旅世界模型 - 旗舰版
===========================
对标大厂产品质感
"""

import os, re, json, sys, socket, urllib.request, ssl, time
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", 
    "sk-4c115205e2c14ca79347838aaeca283a")
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PORT = int(os.environ.get("PORT", 8080))


class SKWMEngine:
    def __init__(self):
        self.catalog = self._load_catalog()
        self.arabic = self._load_arabic()
        self.all = self.catalog + self.arabic
        print(f"  ✅ 总计: {len(self.all)} 篇")
    
    def _load_catalog(self):
        path = DATA_DIR / "literature_catalog.md"
        papers = []
        if not path.exists(): return papers
        try:
            with open(path, 'r', encoding='utf-8') as f: content = f.read()
            lines = content.split('\n'); in_table = False
            for line in lines:
                if '|' in line and '标题' in line: in_table = True; continue
                if in_table and '|---' in line: continue
                if in_table and line.startswith('|'):
                    cols = [c.strip() for c in line.split('|')]
                    if len(cols) >= 5:
                        papers.append({'title': cols[2], 'authors': cols[3], 'year': cols[4],
                            'journal': cols[5] if len(cols)>5 else '',
                            'citations': cols[6] if len(cols)>6 else '0', 'source': '目录'})
                elif in_table and not line.startswith('|'): break
        except: pass
        return papers
    
    def _load_arabic(self):
        path = DATA_DIR / "_arabic_bulk_metadata.json"
        papers = []
        if not path.exists(): return papers
        try:
            with open(path, 'r', encoding='utf-8') as f: content = f.read()
            depth = 0; start = -1
            for i, ch in enumerate(content):
                if ch == '{':
                    if depth == 0: start = i; depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            obj = json.loads(content[start:i+1])
                            if 'title' in obj and obj['title']:
                                obj['source'] = '阿语文献'; papers.append(obj)
                        except: pass
                        start = -1
        except: pass
        seen = set()
        return [p for p in papers if not ((p.get('title',''),p.get('year',''))) in seen 
                and not seen.add((p.get('title',''),p.get('year','')))]
    
    CN_EN = {"中阿":"china arab sino","文旅":"tourism cultural travel","旅游":"tourism travel tourist",
             "文化":"culture cultural","遗产":"heritage","数字化":"digital","阿拉伯":"arab arabic",
             "知识":"knowledge","合作":"cooperation","一带一路":"belt road","研究":"research study","语言":"language"}
    
    def search(self, query, top_k=10):
        query = query.lower().strip()
        if not query: return []
        terms = set(query.split())
        for cn, en in self.CN_EN.items():
            if cn in query: terms.update(en.split())
        scored = []
        for p in self.all:
            title = (p.get('title') or '').lower()
            authors = (p.get('authors') or '').lower()
            score = 0
            for kw in terms:
                if len(kw)<2: continue
                if kw in title: score += 5
                if kw in authors: score += 3
            if score > 0: scored.append({**p, 'score': score})
        scored.sort(key=lambda x: -x['score'])
        return scored[:top_k]
    
    def stats(self):
        years = [int(p['year']) for p in self.all if str(p.get('year','')).isdigit()]
        return {"catalog": len(self.catalog), "arabic": len(self.arabic),
                "total": len(self.all), "year_min": min(years) if years else 0,
                "year_max": max(years) if years else 0,
                "papers_by_year": dict(Counter(years).most_common(25)),
                "top_authors": self._top_authors()}
    
    def _top_authors(self, n=12):
        authors = Counter()
        for p in self.all:
            for name in re.split(r'[,;、]', p.get('authors','')):
                name = name.strip()
                if len(name) > 4 and name[0].isupper():
                    authors[name] += 1
        return authors.most_common(n)

engine = SKWMEngine()


class DeepSeek:
    def __init__(self):
        self.key = DEEPSEEK_KEY
        self.url = "https://api.deepseek.com/v1/chat/completions"
        self.total_cost = 0
    
    def ask(self, messages, temp=0.3, max_tokens=800):
        if not self.key: return None
        payload = json.dumps({"model":"deepseek-chat","messages":messages,
            "temperature":temp,"max_tokens":max_tokens}).encode()
        req = urllib.request.Request(self.url, data=payload,
            headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}, method="POST")
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                data = json.loads(resp.read())
                self.total_cost += data.get("usage",{}).get("total_tokens",0)
                return data["choices"][0]["message"]["content"]
        except: return None
    
    def deep_analyze(self, query, context, summary):
        steps = []
        r1 = self.ask([{"role":"system","content":"你是一个中阿文旅研究专家。请深度拆解用户的研究问题。"},
            {"role":"user","content":f"用户问题: {query}\n\n请用中文分析这个问题背后的学术价值、研究空白和潜在方向。150字内。"}], temp=0.4, max_tokens=350)
        if r1: steps.append(("🎯 问题拆解", r1))
        if summary:
            r2 = self.ask([{"role":"system","content":"你是一个学术情报分析师。"},
                {"role":"user","content":f"查询: {query}\n检索结果: {summary}\n\n分析这个主题的研究趋势、核心发现和值得深入的方向。150字内。"}], temp=0.3, max_tokens=400)
            if r2: steps.append(("📊 趋势洞察", r2))
        r3 = self.ask([{"role":"system","content":"给出简洁有力的研究建议。"},
            {"role":"user","content":f"查询: {query}\n\n给出3条针对性的下一步研究建议，用短句。每行一条。"}], temp=0.5, max_tokens=300)
        if r3: steps.append(("💡 行动建议", r3))
        return steps


ds = DeepSeek()

# ── 全新设计的HTML ──
CSS = r"""
:root {
  --navy: #1a2332;
  --navy-light: #2a3a52;
  --accent: #c9956b;
  --accent-soft: #f8efe7;
  --accent-glow: rgba(201,149,107,0.15);
  --bg: #f7f5f2;
  --card: #ffffff;
  --line: #e8e3dd;
  --text: #1a1a1a;
  --text-light: #7a7268;
  --shadow: 0 1px 3px rgba(26,35,50,0.06), 0 6px 16px rgba(26,35,50,0.04);
  --radius: 12px;
  --font: -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
}

*{margin:0;padding:0;box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;
     display:flex;flex-direction:column;line-height:1.6;-webkit-font-smoothing:antialiased;}

/* ── Header ── */
.topbar{background:var(--navy);color:white;padding:0;position:sticky;top:0;z-index:100;
        backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);}
.topbar-inner{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;align-items:center;height:60px;gap:32px;}
.topbar-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:17px;letter-spacing:-0.3px;white-space:nowrap;}
.topbar-brand span{color:var(--accent);}
.topbar-nav{display:flex;gap:4px;flex:1;}
.nav-btn{background:none;border:none;color:rgba(255,255,255,0.6);padding:8px 14px;border-radius:8px;
         font:500 14px var(--font);cursor:pointer;transition:all 0.2s;white-space:nowrap;}
.nav-btn:hover{color:white;background:rgba(255,255,255,0.08);}
.nav-btn.active{color:white;background:rgba(255,255,255,0.12);}
.topbar-status{font-size:12px;color:rgba(255,255,255,0.4);white-space:nowrap;}
.status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle;}
.status-dot.on{background:#4ade80;box-shadow:0 0 6px rgba(74,222,128,0.4);}
.status-dot.off{background:#888;}

/* ── Main ── */
.main{max-width:1200px;margin:0 auto;padding:32px 24px;flex:1;width:100%;}
.page{display:none;animation:fadeIn .3s ease;}
.page.active{display:block;}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── Hero ── */
.hero{margin-bottom:36px;}
.hero-eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:var(--accent);text-transform:uppercase;margin-bottom:8px;}
.hero h1{font-size:clamp(28px,4vw,44px);font-weight:800;letter-spacing:-.03em;line-height:1.15;margin-bottom:10px;color:var(--navy);}
.hero p{color:var(--text-light);font-size:16px;max-width:600px;}

/* ── Stat Cards ── */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:28px;}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;
      box-shadow:var(--shadow);transition:transform 0.2s;}
.stat:hover{transform:translateY(-2px);}
.stat-number{font-size:28px;font-weight:800;color:var(--navy);letter-spacing:-.03em;line-height:1;}
.stat-label{font-size:13px;color:var(--text-light);margin-top:5px;}

/* ── Grid Panels ── */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;}
@media(max-width:800px){.grid-2{grid-template-columns:1fr;}}

/* ── Card ── */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px;
      box-shadow:var(--shadow);}
.card-title{font-size:15px;font-weight:700;color:var(--navy);margin-bottom:14px;
            padding-bottom:10px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;}
.card-title .badge{font-weight:400;font-size:12px;color:var(--text-light);background:var(--bg);padding:3px 10px;border-radius:20px;}

/* ── Table ── */
.table-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-size:14px;}
th{padding:10px 12px;text-align:left;font-weight:600;color:var(--text-light);font-size:12px;
   text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid var(--line);}
td{padding:10px 12px;border-bottom:1px solid var(--line);font-size:14px;}
tr:last-child td{border-bottom:none;}

/* ── Search ── */
.search-box{display:flex;gap:12px;}
.search-box input{flex:1;padding:12px 16px;border:2px solid var(--line);border-radius:10px;
                  font:15px var(--font);transition:all 0.2s;background:var(--bg);}
.search-box input:focus{border-color:var(--accent);outline:none;box-shadow:0 0 0 3px var(--accent-glow);}
.btn{display:inline-flex;align-items:center;gap:6px;padding:12px 24px;border:none;border-radius:10px;
     font:600 15px var(--font);cursor:pointer;transition:all 0.2s;white-space:nowrap;}
.btn-primary{background:var(--navy);color:white;}
.btn-primary:hover{background:var(--navy-light);transform:translateY(-1px);}
.btn-primary:disabled{background:#ccc;cursor:not-allowed;transform:none;}
.btn-accent{background:var(--accent);color:white;}
.btn-accent:hover{filter:brightness(1.1);transform:translateY(-1px);}

/* ── Results ── */
.result-item{padding:14px 16px;margin:6px 0;border-radius:10px;background:var(--bg);
             border-left:3px solid var(--accent);transition:all 0.15s;}
.result-item:hover{background:var(--accent-soft);}
.result-item .r-title{font-weight:600;font-size:14px;color:var(--navy);}
.result-item .r-meta{font-size:12px;color:var(--text-light);margin-top:4px;display:flex;gap:8px;flex-wrap:wrap;}
.result-item .r-badge{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;
                     background:var(--accent-soft);color:var(--accent);}

/* ── Bar Chart ── */
.bar-chart td:first-child{font-weight:500;width:120px;}
.bar-track{height:22px;background:var(--bg);border-radius:6px;overflow:hidden;position:relative;}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--accent),#dbb08c);border-radius:6px;
          transition:width .6s ease;min-width:4px;}
.bar-label{position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:12px;font-weight:600;color:var(--text-light);}

/* ── DeepSeek Reasoning ── */
.reasoning{border:1px solid var(--line);border-radius:10px;overflow:hidden;}
.r-step{padding:16px 20px;border-bottom:1px solid var(--line);animation:fadeIn .3s ease both;}
.r-step:last-child{border-bottom:none;}
.r-step:nth-child(1){animation-delay:0s;}
.r-step:nth-child(2){animation-delay:.15s;}
.r-step:nth-child(3){animation-delay:.3s;}
.r-step .r-head{font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;}
.r-step .r-body{font-size:14px;line-height:1.7;color:var(--text);}

/* ── Loading ── */
.loading-state{text-align:center;padding:48px 20px;color:var(--text-light);}
.spinner{width:28px;height:28px;border:3px solid var(--line);border-top-color:var(--accent);
         border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 16px;}
@keyframes spin{to{transform:rotate(360deg);}}

/* ── Footer ── */
.footer{text-align:center;padding:32px 24px;color:var(--text-light);font-size:13px;border-top:1px solid var(--line);margin-top:auto;}

/* ── Tables details ── */
table.compact td,table.compact th{padding:8px 10px;font-size:13px;}
"""

HTML_TOP = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🌍 SKWM · 中阿文旅世界模型</title><style>{CSS}</style></head><body>

<div class="topbar">
<div class="topbar-inner">
<div class="topbar-brand"><span>✦</span> SKWM</div>
<nav class="topbar-nav" id="topnav">
<button class="nav-btn active" data-page="dashboard">📊 总览</button>
<button class="nav-btn" data-page="search">🔍 检索</button>
<button class="nav-btn" data-page="analytics">📈 分析</button>
<button class="nav-btn" data-page="arabic">📚 阿语</button>
<button class="nav-btn" data-page="about">ℹ️ 关于</button>
</nav>
<div class="topbar-status"><span class="status-dot {"on" if DEEPSEEK_KEY else "off"}"></span>{'DeepSeek 在线' if DEEPSEEK_KEY else '推理离线'}</div>
</div></div>

<div class="main" id="app">"""

HTML_BOTTOM = r"""
</div>

<footer class="footer">
<p>北京第二外国语学院 · 挑战杯项目 · 基于 World-in-World 闭循环算法</p>
</footer>

<script>
const PAGES = ['dashboard','search','analytics','arabic','about'];

document.getElementById('topnav').addEventListener('click', e => {
  const btn = e.target.closest('.nav-btn');
  if(!btn) return;
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  PAGES.forEach(p=>document.getElementById('page-'+p)?.classList.remove('active'));
  const page = document.getElementById('page-'+btn.dataset.page);
  if(page) page.classList.add('active');
});

function doSearch(type){
  const q = document.getElementById(type+'-q')?.value?.trim();
  if(!q){alert('请输入查询');return;}
  const btn = document.getElementById(type+'-btn');
  const res = document.getElementById(type+'-result');
  btn.disabled=true; btn.textContent='⏳ 分析中...';
  res.innerHTML='<div class="loading-state"><div class="spinner"></div><p>DeepSeek 正在深度推理...</p></div>';
  fetch('/api?type='+type+'&q='+encodeURIComponent(q))
    .then(r=>r.text()).then(html=>{res.innerHTML=html;})
    .catch(e=>{res.innerHTML='<p style="color:red">请求失败</p>';})
    .finally(()=>{btn.disabled=false;btn.innerHTML="✨ 开始分析";});
}

document.querySelectorAll('.search-box input').forEach(inp=>{
  inp.addEventListener('keydown',e=>{if(e.key==='Enter')doSearch(inp.id.replace('-q',''));});
});
</script>
</body></html>"""


def page_dashboard():
    s = engine.stats()
    ds_s = "在线" if DEEPSEEK_KEY else "未配置"
    years_h = "".join(f"<tr><td>{y}</td><td>{c}</td></tr>" for y,c in sorted(s['papers_by_year'].items())[-12:])
    auth_h = "".join(f"<tr><td style='width:24px;color:var(--text-light)'>{i+1}</td><td>{a}</td><td style='text-align:right;font-weight:600'>{c}</td></tr>" for i,(a,c) in enumerate(s['top_authors'][:8]))
    return f"""
<div class="hero"><div class="hero-eyebrow">Scientific Knowledge World Model</div>
<h1>中阿文旅科学知识世界模型</h1><p>基于 World-in-World 闭循环算法 · DeepSeek 深度推理 · {s['total']}篇学术文献</p></div>
<div class="stats">
<div class="stat"><div class="stat-number">{s['total']}</div><div class="stat-label">文献总量</div></div>
<div class="stat"><div class="stat-number">{s['catalog']}</div><div class="stat-label">文献目录</div></div>
<div class="stat"><div class="stat-number">{s['arabic']}</div><div class="stat-label">阿拉伯语文献</div></div>
<div class="stat"><div class="stat-number">{s['year_min']}–{s['year_max']}</div><div class="stat-label">时间跨度</div></div>
<div class="stat"><div class="stat-number">{ds_s}</div><div class="stat-label">DeepSeek 推理</div></div>
</div>
<div class="grid-2">
<div class="card"><div class="card-title">📅 年度发文分布</div><div class="table-wrap"><table class="compact">{years_h}</table></div></div>
<div class="card"><div class="card-title">👥 核心作者</div><div class="table-wrap"><table class="compact">{auth_h}</table></div></div>
</div>
<div class="card"><div class="card-title">🚀 快速开始</div>
<p style="color:var(--text-light);margin-bottom:12px">选择一个功能开始探索中阿文旅知识世界</p>
<div style="display:flex;gap:12px;flex-wrap:wrap">
<button class="btn btn-primary" onclick="document.querySelector('[data-page=search]').click();setTimeout(()=>document.getElementById('search-q')?.focus(),100)">🔍 检索文献</button>
<button class="btn btn-accent" onclick="document.querySelector('[data-page=analytics]').click()">📈 分析热点</button>
<button class="btn btn-primary" onclick="document.querySelector('[data-page=arabic]').click()">📚 阿语文献</button>
</div></div>"""

def page_search():
    return """
<div class="hero"><div class="hero-eyebrow">Literature Discovery</div>
<h1>文献检索</h1><p>智能语义检索 · DeepSeek 深度分析</p></div>
<div class="card" style="padding:18px 24px">
<div class="search-box">
<input id="search-q" placeholder="输入关键词，如：Arabic NLP、文化遗产、digital heritage...">
<button class="btn btn-primary" id="search-btn" onclick="doSearch('search')">✨ 开始分析</button>
</div></div>
<div id="search-result">
<div class="card"><p style="color:var(--text-light);text-align:center;padding:24px">输入关键词，探索 4394 篇文献</p></div></div>"""

def page_analytics():
    return """
<div class="hero"><div class="hero-eyebrow">Research Analytics</div>
<h1>研究分析</h1><p>主题热度 · 研究前沿 · 趋势洞察</p></div>
<div class="card" style="padding:18px 24px">
<div class="search-box">
<input id="analytics-q" placeholder="输入研究方向，如：tourism heritage、文化遗产数字化...">
<button class="btn btn-accent" id="analytics-btn" onclick="doSearch('analytics')">📊 深度分析</button>
</div></div>
<div id="analytics-result">
<div class="card"><p style="color:var(--text-light);text-align:center;padding:24px">输入研究方向，获取深度分析报告</p></div></div>"""

def page_arabic():
    return """
<div class="hero"><div class="hero-eyebrow">Arabic Literature</div>
<h1>阿拉伯语文献</h1><p>探索 4194 篇阿拉伯语学术文献</p></div>
<div class="card" style="padding:18px 24px">
<div class="search-box">
<input id="arabic-q" placeholder="在阿语文献中搜索...">
<button class="btn btn-primary" id="arabic-btn" onclick="doSearch('arabic')">🔍 检索</button>
</div></div>
<div id="arabic-result">
<div class="card"><p style="color:var(--text-light);text-align:center;padding:24px">输入关键词检索阿语文献</p></div></div>"""

def page_about():
    s = engine.stats()
    return f"""
<div class="hero"><div class="hero-eyebrow">About</div>
<h1>关于本平台</h1><p>技术架构与数据来源</p></div>
<div class="grid-2">
<div class="card"><div class="card-title">📋 平台信息</div>
<table class="compact">
<tr><td style="color:var(--text-light)">项目</td><td>中阿文旅科学知识世界模型</td></tr>
<tr><td style="color:var(--text-light)">算法</td><td>World-in-World 闭循环规划</td></tr>
<tr><td style="color:var(--text-light)">推理引擎</td><td>DeepSeek-V3</td></tr>
<tr><td style="color:var(--text-light)">知识库</td><td>{s['total']} 篇文献</td></tr>
<tr><td style="color:var(--text-light)">机构</td><td>北京第二外国语学院</td></tr>
</table></div>
<div class="card"><div class="card-title">📚 数据来源</div>
<table class="compact">
<tr><td style="color:var(--text-light)">文献目录</td><td>{s['catalog']} 篇 (literature_catalog.md)</td></tr>
<tr><td style="color:var(--text-light)">阿语文献</td><td>{s['arabic']} 篇 (OpenAlex)</td></tr>
<tr><td style="color:var(--text-light)">时间跨度</td><td>{s['year_min']} – {s['year_max']} 年</td></tr>
</table></div></div>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/':
            s = engine.stats()
            html = HTML_TOP
            html += f"""<div id="page-dashboard" class="page active">{page_dashboard()}</div>"""
            html += f"""<div id="page-search" class="page">{page_search()}</div>"""
            html += f"""<div id="page-analytics" class="page">{page_analytics()}</div>"""
            html += f"""<div id="page-arabic" class="page">{page_arabic()}</div>"""
            html += f"""<div id="page-about" class="page">{page_about()}</div>"""
            html += HTML_BOTTOM
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        elif path == '/api':
            stype = params.get('type',['search'])[0]
            q = (params.get('q',[''])[0])[:100]
            parts = []
            
            if stype == 'search':
                results = engine.search(q, top_k=10)
                items = "".join(f'''<div class="result-item"><div class="r-title">{r.get("title","")[:80]}</div>
                <div class="r-meta"><span class="r-badge">{r.get("source","")}</span>{r.get("year","")} · {r.get("authors","")[:40]}</div></div>''' for r in results)
                parts.append(f'<div class="card"><div class="card-title">检索结果 <span class="badge">{len(results)} 条</span></div>{items or "<p style=color:var(--text-light)>未找到</p>"}</div>')
                sm = f"检索到{len(results)}篇" if results else "无结果"
                reasoning = ds.deep_analyze(q, "", sm)
                if reasoning:
                    steps = "".join(f'<div class="r-step"><div class="r-head">{h}</div><div class="r-body">{c}</div></div>' for h,c in reasoning)
                    parts.append(f'<div class="card"><div class="card-title">🤖 DeepSeek 深度推理</div><div class="reasoning">{steps}</div></div>')
            
            elif stype == 'analytics':
                results = engine.search(q, top_k=30)
                topics = Counter()
                for p in results:
                    for kw in ["tourism","heritage","culture","digital","arab","language","model","data","AI","education","travel","policy","health","network","knowledge","learning","system","translation","corpus","islamic","media","society"]:
                        if kw in str(p.get('title','')).lower(): topics[kw] += 1
                mx = max((c for _,c in topics.most_common(8)), default=1)
                bars = "".join(f'<tr><td>{t}</td><td><div class="bar-track"><div class="bar-fill" style="width:{c*100//mx}%"></div><span class="bar-label">{c}</span></div></td></tr>' for t,c in topics.most_common(10))
                parts.append(f'<div class="card"><div class="card-title">🔥 主题热度分布 <span class="badge">基于 {len(results)} 篇</span></div><div class="table-wrap"><table class="compact">{bars}</table></div></div>')
                items = "".join(f'<div class="result-item"><div class="r-title">{r.get("title","")[:70]}</div><div class="r-meta">{r.get("year","")} · {r.get("source","")}</div></div>' for r in results[:5])
                parts.append(f'<div class="card"><div class="card-title">📄 代表文献</div>{items}</div>')
                reasoning = ds.deep_analyze(q, f"热度分析: 关键词频次分布", f"分析了{len(results)}篇, {len(topics)}个主题")
                if reasoning:
                    steps = "".join(f'<div class="r-step"><div class="r-head">{h}</div><div class="r-body">{c}</div></div>' for h,c in reasoning)
                    parts.append(f'<div class="card"><div class="card-title">🤖 DeepSeek 深度推理</div><div class="reasoning">{steps}</div></div>')
            
            elif stype == 'arabic':
                results = engine.search(q, top_k=10) if q else engine.arabic[:10]
                s = engine.stats()
                parts.append(f'<div class="stats" style="margin-bottom:16px"><div class="stat"><div class="stat-number">{s["arabic"]}</div><div class="stat-label">阿语文献</div></div></div>')
                items = "".join(f'<div class="result-item"><div class="r-title">{r.get("title","")[:80]}</div><div class="r-meta">{r.get("year","")} · {r.get("arxiv_id","") or ""}</div></div>' for r in results[:10])
                parts.append(f'<div class="card"><div class="card-title">文献列表</div>{items or "<p style=color:var(--text-light)>暂无数据</p>"}</div>')
            
            cost = f'<div style="text-align:right;font-size:12px;color:var(--text-light);margin:8px 4px">💳 {ds.total_cost} tokens</div>' if DEEPSEEK_KEY else ''
            html = "".join(parts) + cost
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        else:
            self.send_response(404); self.send_header('Content-Type','text/plain'); self.end_headers(); self.wfile.write(b'404')
    
    def log_message(self, fmt, *args):
        if '/api' in str(args[0]): print(f"  📡 {args[0]}")


if __name__ == "__main__":
    s = engine.stats()
    print(f"\n{'='*55}")
    print(f"  🌍 中阿文旅世界模型 · 旗舰版")
    print(f"{'='*55}")
    print(f"  📚 {s['total']} 篇文献")
    print(f"  🧠 DeepSeek: {'✅ 已连接' if DEEPSEEK_KEY else '⚠️ 未设置'}")
    print(f"  🌐 http://localhost:{PORT}")
    if 'RAILWAY_PUBLIC_DOMAIN' in os.environ:
        print(f"  🌍 https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}")
    print(f"{'='*55}\n")
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: print("已停止"); server.server_close()
