#!/usr/bin/env python3
"""
🌍 中阿文旅世界模型 - 部署版 (Railway / 任何平台)
====================================================
运行: python3 app.py
部署: 上传到 Railway，自动运行

特点:
- 零外部依赖 (只用 Python 内置模块)
- 知识库路径自动适配 (本地/云端)
- 通过环境变量配置 DeepSeek Key (安全)
"""

import os, re, json, sys, socket
import urllib.request, ssl
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# ====== 配置（通过环境变量覆盖）======

# DeepSeek API Key - 部署时在 Railway 设置环境变量！
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 知识库路径 - 自动适配！
# 本地开发: deploy/data/
# Railway: 同样路径，因为上传了整个文件夹
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# 端口 - Railway 会自动设置 PORT 环境变量
PORT = int(os.environ.get("PORT", 8080))


# ============================================================================
# 知识库引擎
# ============================================================================

class SKWMEngine:
    def __init__(self):
        print(f"  📁 数据目录: {DATA_DIR}")
        self.catalog = self._load_catalog()
        self.arabic = self._load_arabic()
        self.pdfs = []  # PDF太多不打包，部署版仅文本数据
        self.all = self.catalog + self.arabic
        print(f"  ✅ 文献目录: {len(self.catalog)} 篇")
        print(f"  ✅ 阿语文献: {len(self.arabic)} 篇")
        print(f"  ✅ 总计: {len(self.all)} 篇")
        
    def _load_catalog(self):
        path = DATA_DIR / "literature_catalog.md"
        papers = []
        if not path.exists():
            print(f"  ⚠️ 未找到: {path}")
            return papers
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.split('\n')
            in_table = False
            for line in lines:
                if '|' in line and '标题' in line: in_table = True; continue
                if in_table and '|---' in line: continue
                if in_table and line.startswith('|'):
                    cols = [c.strip() for c in line.split('|')]
                    if len(cols) >= 5:
                        papers.append({'title': cols[2], 'authors': cols[3],
                                        'year': cols[4], 'journal': cols[5] if len(cols)>5 else '',
                                        'citations': cols[6] if len(cols)>6 else '0', 'source': '目录'})
                elif in_table and not line.startswith('|'): break
        except Exception as e:
            print(f"  ⚠️ 目录加载: {e}")
        return papers
    
    def _load_arabic(self):
        path = DATA_DIR / "_arabic_bulk_metadata.json"
        papers = []
        if not path.exists():
            print(f"  ⚠️ 未找到: {path}")
            return papers
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            depth = 0; start = -1
            for i, ch in enumerate(content):
                if ch == '{':
                    if depth == 0: start = i
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            obj = json.loads(content[start:i+1])
                            if 'title' in obj and obj['title']:
                                obj['source'] = '阿语文献'
                                papers.append(obj)
                        except: pass
                        start = -1
        except Exception as e:
            print(f"  ⚠️ 阿语加载: {e}")
        # 去重
        seen = set()
        return [p for p in papers if not ((p.get('title',''),p.get('year',''))) in seen and not seen.add((p.get('title',''),p.get('year','')))]
    
    CN_EN = {"中阿":"china arab sino","文旅":"tourism cultural travel","旅游":"tourism travel tourist",
             "文化":"culture cultural","遗产":"heritage","数字化":"digital","阿拉伯":"arab arabic",
             "知识":"knowledge","合作":"cooperation","一带一路":"belt road","研究":"research study"}
    
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
            if score > 0:
                scored.append({**p, 'score': score})
        scored.sort(key=lambda x: -x['score'])
        return scored[:top_k]
    
    def stats(self):
        years = [int(p['year']) for p in self.all if str(p.get('year','')).isdigit()]
        return {"catalog": len(self.catalog), "arabic": len(self.arabic),
                "total": len(self.all),
                "year_min": min(years) if years else 0,
                "year_max": max(years) if years else 0}


engine = SKWMEngine()


# ============================================================================
# DeepSeek API
# ============================================================================

class DeepSeek:
    def __init__(self):
        self.key = DEEPSEEK_KEY
        if not self.key:
            print("  ⚠️ 未设置 DEEPSEEK_API_KEY，推理功能不可用")
        self.url = "https://api.deepseek.com/v1/chat/completions"
        self.total_cost = 0
    
    def ask(self, messages, temp=0.3, max_tokens=800):
        if not self.key:
            return "DeepSeek 未配置，请设置 DEEPSEEK_API_KEY 环境变量"
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
        except Exception as e:
            return f"API错误: {e}"


ds = DeepSeek()


# ============================================================================
# 服务函数
# ============================================================================

def do_service(query, service_type):
    action_labels = {"hotspot":"分析主题热度","search":"检索文献","frontier":"识别研究前沿","arabic":"阿拉伯语文献","stats":"知识库概况"}
    label = action_labels.get(service_type, "检索文献")
    
    result = f"<div class='service-result'><h2>{label}</h2>"
    
    # 1. DeepSeek 规划
    if ds.key:
        plan = ds.ask([
            {"role":"system","content":"你是中阿文旅知识服务专家，简洁回答。"},
            {"role":"user", "content":f"查询:{query}，知识库:{len(engine.all)}篇文献。用1句话说明如何执行。"}
        ], temp=0.5, max_tokens=200)
        result += f"<div class='ds-plan'>🤖 {plan}</div>"
    else:
        result += f"<div class='ds-plan'>📊 直接从知识库检索</div>"
    
    # 2. 知识库查询
    if service_type == "stats":
        s = engine.stats()
        result += f"""
        <div class='data-table'><table>
        <tr><th>项目</th><th>数量</th></tr>
        <tr><td>中阿文旅文献目录</td><td>{s['catalog']} 篇</td></tr>
        <tr><td>阿拉伯语文献</td><td>{s['arabic']} 篇</td></tr>
        <tr><td><strong>总计</strong></td><td><strong>{s['total']} 篇</strong></td></tr>
        <tr><td>时间跨度</td><td>{s['year_min']} - {s['year_max']} 年</td></tr>
        </table></div>"""
    
    elif service_type == "hotspot":
        results = engine.search(query, top_k=20)
        topics = Counter()
        for p in results:
            for kw in ["tourism","heritage","culture","digital","arab","language","model","data","AI","education","travel","policy"]:
                if kw in str(p.get('title','')).lower(): topics[kw] += 1
        result += f"<p>基于 {len(results)} 篇相关文献分析</p><table><tr><th>主题</th><th>频次</th></tr>"
        for t, c in topics.most_common(10):
            bar = "█" * min(c, 15)
            result += f"<tr><td>{t}</td><td>{bar} {c}</td></tr>"
        result += "</table><h3>📄 代表文献</h3><ul>"
        for p in results[:5]:
            result += f"<li>{p.get('title','')[:70]} ({p.get('year','')})</li>"
        result += "</ul>"
    
    elif service_type == "search":
        results = engine.search(query, top_k=10)
        result += f"<p>命中 {len(results)} 条</p><ul>"
        for p in results:
            result += f"<li><strong>{p.get('title','')[:80]}</strong> ({p.get('year','')})<br><small>{p.get('authors','')[:40]} | {p.get('source','')}</small></li>"
        result += "</ul>"
    
    elif service_type == "frontier":
        recent = [p for p in engine.all if str(p.get('year','')).isdigit() and int(p.get('year',0)) >= 2023]
        result += f"<p>近3年文献: {len(recent)} 篇</p><ul>"
        for p in sorted(recent, key=lambda x: -int(x.get('year',0)))[:10]:
            result += f"<li>{p.get('title','')[:70]} ({p.get('year','')})</li>"
        result += "</ul>"
    
    elif service_type == "arabic":
        result += f"<p>阿语文献: {len(engine.arabic)} 篇</p><ul>"
        for p in engine.arabic[:10]:
            result += f"<li>{p.get('title','')[:70]} ({p.get('year','')})</li>"
        result += "</ul>"
    
    # 3. DeepSeek 总结
    if ds.key:
        summary = ds.ask([
            {"role":"system","content":"用2-3句话总结发现和建议。"},
            {"role":"user","content":f"查询:{query} 类型:{service_type}"}
        ], temp=0.3, max_tokens=400)
        result += f"<div class='ds-summary'>🔍 {summary}</div>"
    
    result += f"<div class='cost'>💳 消耗: {ds.total_cost} tokens</div></div>"
    return result


# ============================================================================
# HTML 页面（内置在代码中，无需额外文件）
# ============================================================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌍 中阿文旅世界模型</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
     background:linear-gradient(135deg,#f7f5f0,#efe6d8);min-height:100vh;color:#333;}
.header{background:linear-gradient(135deg,#8B4513,#A0522D);color:white;padding:30px 20px;text-align:center;}
.header h1{font-size:28px;margin-bottom:8px;}
.container{max-width:1000px;margin:20px auto;padding:0 15px;}
.stats-bar{background:white;border-radius:12px;padding:15px;margin-bottom:20px;
            box-shadow:0 2px 8px rgba(0,0,0,0.08);display:flex;justify-content:space-around;flex-wrap:wrap;}
.stat-item{text-align:center;padding:5px 15px;}
.stat-num{font-size:24px;font-weight:bold;color:#8B4513;}
.stat-label{font-size:12px;color:#666;}
.search-box{background:white;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);}
.search-box input[type=text]{width:100%;padding:12px;border:2px solid #ddd;border-radius:8px;font-size:16px;}
.search-box input[type=text]:focus{border-color:#8B4513;outline:none;}
.radio-group{display:flex;gap:10px;margin:15px 0;flex-wrap:wrap;}
.radio-group label{padding:8px 16px;background:#f0ebe3;border-radius:20px;cursor:pointer;font-size:14px;transition:all .3s;}
.radio-group input[type=radio]{display:none;}
.radio-group input[type=radio]:checked+label{background:#8B4513;color:#fff;}
.search-btn{background:#8B4513;color:white;border:none;padding:12px 30px;border-radius:8px;font-size:16px;cursor:pointer;}
.search-btn:hover{background:#A0522D;}
.search-btn:disabled{background:#ccc;cursor:not-allowed;}
.result-box{background:white;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);min-height:100px;}
.service-result h2{color:#8B4513;margin-bottom:15px;border-bottom:2px solid #D4A574;padding-bottom:8px;}
.service-result table{width:100%;border-collapse:collapse;margin:10px 0;}
.service-result td,.service-result th{padding:8px;text-align:left;border-bottom:1px solid #eee;}
.service-result ul{margin:10px 0;padding-left:20px;}
.service-result li{margin:8px 0;line-height:1.5;}
.ds-plan,.ds-summary{background:#f0ebe3;padding:12px 15px;border-radius:8px;margin:10px 0;border-left:4px solid #8B4513;line-height:1.6;}
.cost{text-align:right;font-size:12px;color:#999;margin-top:10px;}
.footer{text-align:center;padding:20px;color:#999;font-size:12px;}
.loading{text-align:center;padding:40px;color:#8B4513;font-size:18px;}
</style>
</head>
<body>
<div class="header">
<h1>🌍 中阿文旅科学知识世界模型</h1>
<p>World-in-World 算法 + DeepSeek 推理 + sk-wm 知识库</p>
</div>
<div class="container">
<div class="stats-bar" id="stats-bar">加载中...</div>
<div class="search-box">
<input type="text" id="query" placeholder="输入研究问题，例如: 中阿文化遗产旅游、Arabic NLP、文旅融合..." onkeydown="if(event.key==='Enter')search()">
<div class="radio-group" id="types"></div>
<button class="search-btn" id="btn" onclick="search()">🚀 开始分析</button>
</div>
<div class="result-box" id="result">
<p style="color:#999;text-align:center;padding:40px;">输入问题，开始探索中阿文旅知识世界 🌍</p>
</div>
</div>
<div class="footer"><p>基于 World-in-World 论文 · 北京第二外国语学院挑战杯项目</p></div>
<script>
const TYPES=[
{id:'hotspot',label:'🔥 热点分析'},
{id:'search',label:'📄 文献检索'},
{id:'frontier',label:'📈 研究前沿'},
{id:'arabic',label:'📚 阿语文献'},
{id:'stats',label:'📊 知识库概况'}
];
window.onload=function(){
const g=document.getElementById('types');
TYPES.forEach((t,i)=>{
const d=document.createElement('div');
d.innerHTML='<input type="radio" name="t" value="'+t.id+'" id="t'+t.id+'"'+(i===0?'checked':'')+'><label for="t'+t.id+'">'+t.label+'</label>';
g.appendChild(d);
});
fetch('/api?type=stats').then(r=>r.text()).then(h=>document.getElementById('stats-bar').innerHTML=h);
};
function search(){
const q=document.getElementById('query').value.trim();
if(!q){alert('请输入查询');return;}
const t=document.querySelector('input[name="t"]:checked').value;
const btn=document.getElementById('btn');
const box=document.getElementById('result');
btn.disabled=true;btn.textContent='⏳ 分析中...';
box.innerHTML='<div class="loading">🤔 DeepSeek 正在思考...</div>';
fetch('/api?type='+t+'&q='+encodeURIComponent(q))
.then(r=>r.text()).then(h=>{box.innerHTML=h;})
.catch(e=>{box.innerHTML='<p style="color:red">错误: '+e.message+'</p>';})
.finally(()=>{btn.disabled=false;btn.textContent='🚀 开始分析';});
}
</script>
</body>
</html>"""


# ============================================================================
# Web 服务器
# ============================================================================

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        
        elif path == '/api':
            params = parse_qs(parsed.query)
            stype = params.get('type', ['stats'])[0]
            query = params.get('q', [''])[0]
            
            if stype == 'stats':
                s = engine.stats()
                html = f"""
                <div class="stat-item"><div class="stat-num">{s['total']}</div><div class="stat-label">总计文献</div></div>
                <div class="stat-item"><div class="stat-num">{s['catalog']}</div><div class="stat-label">文献目录</div></div>
                <div class="stat-item"><div class="stat-num">{s['arabic']}</div><div class="stat-label">阿语文献</div></div>
                <div class="stat-item"><div class="stat-num">{s['year_min']}-{s['year_max']}</div><div class="stat-label">时间跨度</div></div>
                """
            else:
                html = do_service(query, stype)
            
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
        if '/api' in str(args[0]):
            print(f"  📡 {args[0]}")
        elif '/' == str(args[0]):
            print(f"  🌐 页面访问")


# ============================================================================
# 启动
# ============================================================================

if __name__ == "__main__":
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "127.0.0.1"
    
    print(f"\n{'='*60}")
    print(f"🌍 中阿文旅世界模型")
    print(f"{'='*60}")
    print(f"\n📚 知识库: {engine.stats()['total']} 篇文献")
    print(f"🔑 DeepSeek: {'已连接' if ds.key else '未设置(仅知识库查询)'}")
    print(f"\n🌐 访问地址:")
    print(f"   本地: http://localhost:{PORT}")
    print(f"   网络: http://{ip}:{PORT}")
    if 'RAILWAY_PUBLIC_DOMAIN' in os.environ:
        print(f"   🌍 https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}")
    print(f"\n📝 提示:")
    print(f"   - 环境变量 DEEPSEEK_API_KEY 可选，不设置则只能查知识库")
    print(f"   - 环境变量 PORT 可选，默认 8080")
    print(f"\n按 Ctrl+C 停止")
    print(f"{'='*60}\n")
    
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()
