#!/usr/bin/env python3
"""
🌍 中阿文旅世界模型 - 专业平台版
=================================
多UI集成 + 深度DeepSeek推理展示
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
                "papers_by_year": dict(Counter(years).most_common(20)),
                "top_authors": self._top_authors()}
    
    def _top_authors(self, n=15):
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
    
    def deep_analyze(self, query, context, results_summary):
        """深度推理：多步分析"""
        steps = []
        
        # Step 1: 问题理解
        r1 = self.ask([
            {"role":"system","content":"你是中阿文旅研究专家。请分析用户问题的研究价值。"},
            {"role":"user","content":f"用户问题: {query}\n\n请拆解这个问题背后的研究需求。100字内。"}
        ], temp=0.4, max_tokens=300)
        if r1: steps.append(("🔍 问题理解", r1))
        
        # Step 2: 知识检索策略
        if engine.all:
            r2 = self.ask([
                {"role":"system","content":"你是一个检索策略专家。"},
                {"role":"user","content":f"查询: {query}\n知识库: {len(engine.all)}篇文献\n\n设计最佳检索关键词组合。"}
            ], temp=0.3, max_tokens=300)
            if r2: steps.append(("🎯 检索策略", r2))
        
        # Step 3: 结果分析
        if results_summary:
            r3 = self.ask([
                {"role":"system","content":"分析知识库返回的结果，给出深度洞察。"},
                {"role":"user","content":f"查询: {query}\n结果摘要: {results_summary}\n\n分析结果中的关键发现、研究空白和趋势。"}
            ], temp=0.3, max_tokens=500)
            if r3: steps.append(("📊 结果分析", r3))
        
        # Step 4: 建议
        r4 = self.ask([
            {"role":"system","content":"给出可操作的研究建议。"},
            {"role":"user","content":f"查询: {query}\n\n请给出3条针对性的研究建议，每条一行。"}
        ], temp=0.5, max_tokens=400)
        if r4: steps.append(("💡 研究建议", r4))
        
        return steps

ds = DeepSeek()


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌍 中阿文旅世界模型</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}

:root {
  --primary: #8B4513;
  --primary-light: #A0522D;
  --primary-dark: #6B3410;
  --bg: #f5f2ed;
  --card: #ffffff;
  --border: #e5ddd4;
  --text: #2c1810;
  --text-light: #7a6a5c;
  --accent: #D4A574;
  --shadow: 0 2px 12px rgba(0,0,0,0.06);
}

body{font-family:'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
     background:var(--bg);color:var(--text);min-height:100vh;display:flex;}

/* 侧边栏 */
.sidebar{width:240px;background:linear-gradient(180deg,var(--primary) 0%,var(--primary-dark) 100%);
         color:white;padding:24px 0;display:flex;flex-direction:column;position:fixed;height:100vh;z-index:10;}
.sidebar-logo{padding:0 20px 20px;border-bottom:1px solid rgba(255,255,255,0.15);margin-bottom:12px;}
.sidebar-logo h1{font-size:18px;margin-bottom:4px;}
.sidebar-logo p{font-size:11px;opacity:0.7;}
.nav-item{padding:12px 20px;cursor:pointer;display:flex;align-items:center;gap:10px;
           font-size:14px;transition:all 0.2s;border-left:3px solid transparent;}
.nav-item:hover{background:rgba(255,255,255,0.08);}
.nav-item.active{background:rgba(255,255,255,0.12);border-left-color:var(--accent);font-weight:600;}
.nav-item .icon{font-size:18px;width:24px;text-align:center;}
.sidebar-footer{margin-top:auto;padding:12px 20px;font-size:11px;opacity:0.5;}

/* 主内容 */
.main{margin-left:240px;flex:1;padding:24px 32px;max-width:1200px;}

/* 页面标题 */
.page-header{margin-bottom:24px;}
.page-header h2{font-size:24px;color:var(--primary-dark);margin-bottom:4px;}
.page-header p{color:var(--text-light);font-size:14px;}

/* 卡片 */
.card{background:var(--card);border-radius:12px;padding:20px;margin-bottom:16px;
      box-shadow:var(--shadow);border:1px solid var(--border);}
.card-title{font-size:15px;font-weight:600;color:var(--primary-dark);margin-bottom:12px;
            padding-bottom:8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;}

/* 统计 */
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px;}
.stat-card{background:var(--card);border-radius:10px;padding:16px;text-align:center;
           box-shadow:var(--shadow);border:1px solid var(--border);}
.stat-num{font-size:28px;font-weight:bold;color:var(--primary);}
.stat-label{font-size:12px;color:var(--text-light);margin-top:4px;}

/* 搜索 */
.search-bar{display:flex;gap:12px;margin-bottom:16px;}
.search-bar input{flex:1;padding:12px 16px;border:2px solid var(--border);border-radius:8px;
                  font-size:15px;transition:border-color 0.3s;}
.search-bar input:focus{border-color:var(--primary);outline:none;}
.search-bar select{padding:12px;border:2px solid var(--border);border-radius:8px;
                   background:white;font-size:14px;min-width:130px;}
.search-bar button{padding:12px 28px;background:var(--primary);color:white;border:none;
                   border-radius:8px;font-size:15px;cursor:pointer;transition:background 0.3s;white-space:nowrap;}
.search-bar button:hover{background:var(--primary-light);}
.search-bar button:disabled{background:#ccc;cursor:not-allowed;}

/* 结果 */
.result-item{padding:14px;margin:8px 0;border-radius:8px;background:#faf8f5;
             border-left:3px solid var(--accent);transition:background 0.2s;}
.result-item:hover{background:#f5f0e8;}
.result-item .title{font-weight:600;font-size:14px;color:var(--text);}
.result-item .meta{font-size:12px;color:var(--text-light);margin-top:4px;}
.result-item .badge{display:inline-block;padding:2px 8px;border-radius:4px;
                    font-size:11px;background:var(--accent);color:white;margin-right:6px;}

/* DeepSeek 推理面板 */
.thinking-panel{background:#faf8f5;border-radius:8px;border:1px solid var(--border);margin:12px 0;}
.thinking-step{padding:14px 16px;border-bottom:1px solid var(--border);}
.thinking-step:last-child{border-bottom:none;}
.thinking-step .step-header{font-weight:600;font-size:13px;color:var(--primary);margin-bottom:6px;}
.thinking-step .step-body{font-size:13px;line-height:1.6;color:var(--text);}

/* 表格 */
table{width:100%;border-collapse:collapse;font-size:13px;}
th{padding:10px 12px;text-align:left;background:#faf8f5;color:var(--text-light);font-weight:600;border-bottom:2px solid var(--border);}
td{padding:10px 12px;border-bottom:1px solid var(--border);}
tr:hover td{background:#faf8f5;}

/* 隐藏控制 */
.page{display:none;}
.page.active{display:block;}

/* 负载动画 */
.loading{text-align:center;padding:40px;color:var(--text-light);}
.spinner{display:inline-block;width:24px;height:24px;border:3px solid var(--border);
          border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}

/* 标签 */
.tabs{display:flex;gap:4px;margin-bottom:16px;flex-wrap:wrap;}
.tab-btn{padding:8px 16px;border-radius:6px;border:1px solid var(--border);
         background:white;cursor:pointer;font-size:13px;transition:all 0.2s;}
.tab-btn.active{background:var(--primary);color:white;border-color:var(--primary);}
.tab-btn:hover:not(.active){background:#f5f0e8;}

@media(max-width:768px){
  .sidebar{width:60px;}.sidebar-logo h1,.sidebar-logo p,.nav-item span{display:none;}
  .main{margin-left:60px;padding:16px;}.search-bar{flex-wrap:wrap;}
  .search-bar select{width:100%;}
}
</style>
</head>
<body>

<div class="sidebar">
  <div class="sidebar-logo">
    <h1>🌍 SKWM</h1>
    <p>中阿文旅世界模型</p>
  </div>
  <div class="nav-item active" onclick="switchPage('dashboard',this)">
    <span class="icon">📊</span><span>仪表盘</span>
  </div>
  <div class="nav-item" onclick="switchPage('search',this)">
    <span class="icon">🔍</span><span>文献检索</span>
  </div>
  <div class="nav-item" onclick="switchPage('hotspot',this)">
    <span class="icon">🔥</span><span>热点分析</span>
  </div>
  <div class="nav-item" onclick="switchPage('frontier',this)">
    <span class="icon">📈</span><span>研究前沿</span>
  </div>
  <div class="nav-item" onclick="switchPage('arabic',this)">
    <span class="icon">📚</span><span>阿语文献</span>
  </div>
  <div class="nav-item" onclick="switchPage('about',this)">
    <span class="icon">ℹ️</span><span>关于</span>
  </div>
  <div class="sidebar-footer">
    <div>总文献: ___TOTAL___ 篇</div>
    <div>DeepSeek: ___DS_STATUS___</div>
  </div>
</div>

<div class="main">
<div id="page-dashboard" class="page active">___DASHBOARD___</div>
<div id="page-search" class="page">___SEARCH___</div>
<div id="page-hotspot" class="page">___HOTSPOT___</div>
<div id="page-frontier" class="page">___FRONTIER___</div>
<div id="page-arabic" class="page">___ARABIC___</div>
<div id="page-about" class="page">___ABOUT___</div>
</div>

<script>
function switchPage(id,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(el) el.classList.add('active');
}

function doSearch(page){
  const q = document.getElementById(page+'-q').value.trim();
  if(!q){alert('请输入查询');return;}
  const btn = document.getElementById(page+'-btn');
  const res = document.getElementById(page+'-result');
  btn.disabled=true; btn.textContent='⏳ 分析中...';
  res.innerHTML='<div class="loading"><div class="spinner"></div><p style="margin-top:12px">🤔 DeepSeek 正在深度推理...</p></div>';
  
  // 先执行知识库查询
  fetch('/api?type='+page+'&q='+encodeURIComponent(q))
    .then(r=>r.text())
    .then(html=>{res.innerHTML=html;})
    .catch(e=>{res.innerHTML='<p style="color:red">错误: '+e.message+'</p>';})
    .finally(()=>{btn.disabled=false; btn.textContent='🚀 开始分析';});
}

function switchTab(group, tab, el){
  document.querySelectorAll('.'+group+'-tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.'+group+'-content').forEach(c=>c.style.display='none');
  document.getElementById(group+'-'+tab).style.display='block';
  el.classList.add('active');
}
</script>
</body>
</html>"""


def build_dashboard():
    s = engine.stats()
    authors_html = "".join(f"<tr><td>{i+1}</td><td>{a}</td><td>{c}</td></tr>" for i,(a,c) in enumerate(s['top_authors'][:10]))
    years_html = "".join(f"<tr><td>{y}</td><td>{c}</td></tr>" for y,c in sorted(s['papers_by_year'].items())[-15:][::-1])
    ds_status = "✅ 已连接" if DEEPSEEK_KEY else "⚠️ 未设置"
    
    return f"""
    <div class="page-header"><h2>📊 知识库仪表盘</h2><p>中阿文旅科学知识世界模型总览</p></div>
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-num">{s['total']}</div><div class="stat-label">总文献数</div></div>
      <div class="stat-card"><div class="stat-num">{s['catalog']}</div><div class="stat-label">文献目录</div></div>
      <div class="stat-card"><div class="stat-num">{s['arabic']}</div><div class="stat-label">阿语文献</div></div>
      <div class="stat-card"><div class="stat-num">{s['year_min']}-{s['year_max']}</div><div class="stat-label">时间跨度</div></div>
      <div class="stat-card"><div class="stat-num">{ds_status.split()[0]}</div><div class="stat-label">DeepSeek</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div class="card"><div class="card-title">📅 文献年份分布</div><table><tr><th>年份</th><th>数量</th></tr>{years_html}</table></div>
      <div class="card"><div class="card-title">👥 高产作者 TOP10</div><table><tr><th>#</th><th>作者</th><th>篇数</th></tr>{authors_html}</table></div>
    </div>
    <script>document.querySelector('.sidebar-footer div:last-child').textContent='DeepSeek: {ds_status}';</script>
    """
    return html

def build_search_page():
    return """
    <div class="page-header"><h2>🔍 文献检索</h2><p>从4394篇文献中智能检索</p></div>
    <div class="card">
      <div class="search-bar">
        <input id="search-q" placeholder="输入检索词，如: Arabic NLP, 文化遗产, tourism heritage..." onkeydown="if(event.key==='Enter')doSearch('search')">
        <button id="search-btn" onclick="doSearch('search')">🚀 开始分析</button>
      </div>
    </div>
    <div id="search-result"><div class="card"><p style="color:var(--text-light);text-align:center;padding:20px;">输入关键词开始检索</p></div></div>
    """

def build_hotspot_page():
    return """
    <div class="page-header"><h2>🔥 热点分析</h2><p>识别研究主题热度分布</p></div>
    <div class="card">
      <div class="search-bar">
        <input id="hotspot-q" placeholder="输入研究方向，如: 文化遗产旅游, Arabic NLP..." onkeydown="if(event.key==='Enter')doSearch('hotspot')">
        <button id="hotspot-btn" onclick="doSearch('hotspot')">🔥 分析热度</button>
      </div>
    </div>
    <div id="hotspot-result"><div class="card"><p style="color:var(--text-light);text-align:center;padding:20px;">输入研究方向开始分析</p></div></div>
    """

def build_frontier_page():
    return """
    <div class="page-header"><h2>📈 研究前沿</h2><p>近3年新兴研究方向识别</p></div>
    <div class="card">
      <div class="search-bar">
        <input id="frontier-q" placeholder="输入研究方向，留空则看全局前沿" onkeydown="if(event.key==='Enter')doSearch('frontier')">
        <button id="frontier-btn" onclick="doSearch('frontier')">📈 识别前沿</button>
      </div>
    </div>
    <div id="frontier-result"><div class="card"><p style="color:var(--text-light);text-align:center;padding:20px;">输入研究方向开始分析</p></div></div>
    """

def build_arabic_page():
    return """
    <div class="page-header"><h2>📚 阿拉伯语文献</h2><p>探索阿语文献数据</p></div>
    <div class="card">
      <div class="search-bar">
        <input id="arabic-q" placeholder="在阿语文献中搜索..." onkeydown="if(event.key==='Enter')doSearch('arabic')">
        <button id="arabic-btn" onclick="doSearch('arabic')">📚 检索</button>
      </div>
    </div>
    <div id="arabic-result"><div class="card"><p style="color:var(--text-light);text-align:center;padding:20px;">输入关键词检索阿语文献</p></div></div>
    """

def build_about_page():
    return f"""
    <div class="page-header"><h2>ℹ️ 关于本平台</h2></div>
    <div class="card">
      <h3 style="color:var(--primary);margin-bottom:12px;">🌍 中阿文旅科学知识世界模型</h3>
      <p style="line-height:1.8;margin-bottom:16px;">基于 <strong>World-in-World</strong> (arXiv:2510.18135) 闭循环规划算法构建的知识服务系统。<br>
      融合 <strong>DeepSeek 大模型推理</strong> + <strong>sk-wm 真实知识库</strong> (4394篇文献) 提供智能学科服务。</p>
      <table>
        <tr><td>📚 知识库规模</td><td>{engine.stats()['total']} 篇文献</td></tr>
        <tr><td>📁 数据来源</td><td>literature_catalog.md + _arabic_bulk_metadata.json</td></tr>
        <tr><td>🧠 推理引擎</td><td>DeepSeek-V3 (API)</td></tr>
        <tr><td>🌐 部署平台</td><td>Railway</td></tr>
        <tr><td>📍 所属机构</td><td>北京第二外国语学院 · 挑战杯项目</td></tr>
      </table>
    </div>
    """


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            html = HTML
            s = engine.stats()
            ds_status = "在线 ✅" if DEEPSEEK_KEY else "未配置 ⚠️"
            html = html.replace("___TOTAL___", str(s['total']))
            html = html.replace("___DS_STATUS___", ds_status)
            html = html.replace("___DASHBOARD___", build_dashboard())
            html = html.replace("___SEARCH___", build_search_page())
            html = html.replace("___HOTSPOT___", build_hotspot_page())
            html = html.replace("___FRONTIER___", build_frontier_page())
            html = html.replace("___ARABIC___", build_arabic_page())
            html = html.replace("___ABOUT___", build_about_page())
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        elif path == '/api':
            params = parse_qs(parsed.query)
            stype = params.get('type', ['search'])[0]
            query = params.get('q', [''])[0]
            q = query[:100]
            
            result_parts = []
            
            # 1. 知识库检索
            if stype == 'search':
                results = engine.search(q, top_k=10)
                items = "".join(f'''<div class="result-item">
                    <div class="title">{r.get('title','')[:80]}</div>
                    <div class="meta"><span class="badge">{r.get('source','')}</span> {r.get('authors','')[:40]} | {r.get('year','')} | 引用:{r.get('citations','0')}</div>
                </div>''' for r in results)
                result_parts.append(f'<div class="card"><div class="card-title">📄 检索结果 <span style="font-weight:normal;font-size:13px">命中 {len(results)} 条</span></div>{items or "<p style=color:var(--text-light)>未找到相关文献</p>"}</div>')
                
                # 深度推理
                summary = f"检索到{len(results)}篇文献" if results else "未命中"
                reasoning = ds.deep_analyze(q, "", summary)
                if reasoning:
                    steps_html = "".join(f'<div class="thinking-step"><div class="step-header">{h}</div><div class="step-body">{c}</div></div>' for h,c in reasoning)
                    result_parts.append(f'<div class="card"><div class="card-title">🤖 DeepSeek 深度推理</div><div class="thinking-panel">{steps_html}</div></div>')
            
            elif stype == 'hotspot':
                results = engine.search(q, top_k=30)
                topics = Counter()
                for p in results:
                    for kw in ["tourism","heritage","culture","digital","arab","language","model","data","AI","education","travel","policy","health","social","network","knowledge","learning","system","translation","corpus"]:
                        if kw in str(p.get('title','')).lower(): topics[kw] += 1
                bar_chart = "".join(f'<tr><td>{t}</td><td><div style="background:var(--accent);height:20px;width:{min(c*100//max(m for _,m in topics.most_common(10)) if topics else 1, 100)}%;border-radius:4px;min-width:20px"></div></td><td>{c}</td></tr>' for t,c in topics.most_common(12))
                result_parts.append(f'<div class="card"><div class="card-title">🔥 主题热度 <span style="font-weight:normal;font-size:13px">基于{len(results)}篇文献</span></div><table><tr><th>主题</th><th>分布</th><th>频次</th></tr>{bar_chart}</table></div>')
                
                items = "".join(f'<div class="result-item"><div class="title">{r.get("title","")[:70]}</div><div class="meta">{r.get("year","")} | {r.get("source","")}</div></div>' for r in results[:5])
                result_parts.append(f'<div class="card"><div class="card-title">📄 代表文献</div>{items}</div>')
                
                reasoning = ds.deep_analyze(q, f"热度分析: 关键词频次分布", f"分析了{len(results)}篇文献，{len(topics)}个主题")
                if reasoning:
                    steps_html = "".join(f'<div class="thinking-step"><div class="step-header">{h}</div><div class="step-body">{c}</div></div>' for h,c in reasoning)
                    result_parts.append(f'<div class="card"><div class="card-title">🤖 DeepSeek 深度推理</div><div class="thinking-panel">{steps_html}</div></div>')
            
            elif stype == 'frontier':
                results = engine.search(q, top_k=20) if q else []
                all_recent = [p for p in engine.all if str(p.get('year','')).isdigit() and int(p.get('year',0)) >= 2023]
                recent = results if q and results else all_recent
                items = "".join(f'<div class="result-item"><div class="title">{r.get("title","")[:80]}</div><div class="meta">{r.get("year","")} | {r.get("source","")} | {r.get("authors","")[:30]}</div></div>' for r in sorted(recent, key=lambda x: -int(x.get('year',0)))[:12])
                result_parts.append(f'<div class="card"><div class="card-title">📈 近3年文献 <span style="font-weight:normal;font-size:13px">共{len(all_recent)}篇</span></div>{items}</div>')
                reasoning = ds.deep_analyze(q or "中阿文旅前沿", f"近3年有{len(all_recent)}篇文献", f"前沿分析")
                if reasoning:
                    steps_html = "".join(f'<div class="thinking-step"><div class="step-header">{h}</div><div class="step-body">{c}</div></div>' for h,c in reasoning)
                    result_parts.append(f'<div class="card"><div class="card-title">🤖 DeepSeek 前沿分析</div><div class="thinking-panel">{steps_html}</div></div>')
            
            elif stype == 'arabic':
                results = engine.search(q, top_k=10) if q else engine.arabic[:10]
                s = engine.stats()
                result_parts.append(f'<div class="card"><div class="card-title">📚 阿语文献概况 <span style="font-weight:normal;font-size:13px">总计{s["arabic"]}篇</span></div></div>')
                items = "".join(f'<div class="result-item"><div class="title">{r.get("title","")[:80]}</div><div class="meta">{r.get("year","")} | {r.get("source","")} | arXiv:{r.get("arxiv_id","")}</div></div>' for r in results[:10])
                result_parts.append(f'<div class="card"><div class="card-title">📄 样本文献</div>{items or "<p style=color:var(--text-light)>暂无数据</p>"}</div>')
            
            cost_info = f'<div class="card" style="text-align:right;font-size:12px;color:var(--text-light);padding:10px 16px">💳 累计消耗: {ds.total_cost} tokens (约¥{ds.total_cost/1e6*2:.4f})</div>' if DEEPSEEK_KEY else ''
            
            html = "".join(result_parts) + cost_info
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'404')
    
    def log_message(self, fmt, *args):
        if '/api' in str(args[0]): print(f"  📡 {args[0]}")


if __name__ == "__main__":
    s = engine.stats()
    hostname = socket.gethostname()
    try: ip = socket.gethostbyname(hostname)
    except: ip = "127.0.0.1"
    
    print(f"\n{'='*60}")
    print(f"🌍 中阿文旅世界模型 - 专业平台")
    print(f"{'='*60}")
    print(f"\n📚 知识库: {s['total']} 篇 (目录{s['catalog']}+阿语{s['arabic']})")
    print(f"🧠 DeepSeek: {'已连接' if DEEPSEEK_KEY else '未设置'}")
    print(f"\n🌐 http://localhost:{PORT}")
    if 'RAILWAY_PUBLIC_DOMAIN' in os.environ:
        print(f"🌍 https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}")
    print(f"\n按 Ctrl+C 停止\n{'='*60}\n")
    
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: print("\n已停止"); server.server_close()
