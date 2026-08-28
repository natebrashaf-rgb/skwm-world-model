#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿语文献人工验证Web工具
======================
使用方法：
  1. 运行: python human_verification_app.py
  2. 打开浏览器: http://localhost:5000
  3. 逐篇查看文献并标记分类
  4. 结果自动保存到 output/verification_results.json
"""
from flask import Flask, render_template, jsonify, request
import json
import re
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# ============================================================
# 数据加载
# ============================================================
DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

def load_b1():
    """加载B1文献主表"""
    raw = open(DATA_DIR / "B1_文献主表.json", encoding='utf-8').read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)

def load_arabic_texts():
    """加载阿语文本库"""
    path = DATA_DIR / "pdf_texts_arabic_20260819.json"
    if path.exists():
        return json.load(open(path, encoding='utf-8'))
    return {}

def load_verification_results():
    """加载已验证结果"""
    path = OUTPUT_DIR / "verification_results.json"
    if path.exists():
        return json.load(open(path, encoding='utf-8'))
    return {}

def save_verification_results(results):
    """保存验证结果"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "verification_results.json", "w", encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

# ============================================================
# 全局数据
# ============================================================
B1_DATA = load_b1()
ARABIC_TEXTS = load_arabic_texts()

# 加载DOI验证结果，只保留已验证的阿语文献
def load_verified_dois():
    """加载已验证的DOI列表"""
    path = OUTPUT_DIR / "arabic_papers_verification.json"
    if path.exists():
        data = json.load(open(path, encoding='utf-8'))
        verified_dois = set()
        for r in data.get("details", {}).get("verified", []):
            if r.get("doi"):
                verified_dois.add(r["doi"])
        return verified_dois
    return set()

VERIFIED_DOIS = load_verified_dois()
ARABIC_PAPERS = [p for p in B1_DATA if p.get("language") == "ar" and p.get("doi") in VERIFIED_DOIS]

# ============================================================
# 路由
# ============================================================
@app.route('/')
def index():
    """主页"""
    return render_template('index.html', total=len(ARABIC_PAPERS))

@app.route('/api/papers')
def get_papers():
    """获取所有阿语文献列表"""
    papers = []
    for i, p in enumerate(ARABIC_PAPERS):
        doi = p.get("doi", "")
        title = p.get("title", "")
        
        # 获取全文
        full_text = ""
        if doi and doi in ARABIC_TEXTS:
            full_text = ARABIC_TEXTS[doi][:500]  # 取前500字符
        
        papers.append({
            "index": i,
            "doi": doi,
            "title": title,
            "year": p.get("year"),
            "keywords": p.get("keywords", []),
            "has_pdf": bool(p.get("has_pdf")),
            "text_preview": full_text,
        })
    
    return jsonify({"papers": papers})

@app.route('/api/paper/<int:index>')
def get_paper(index):
    """获取单篇文献详情"""
    if index < 0 or index >= len(ARABIC_PAPERS):
        return jsonify({"error": "Invalid index"}), 404
    
    p = ARABIC_PAPERS[index]
    doi = p.get("doi", "")
    
    # 获取完整全文
    full_text = ""
    if doi and doi in ARABIC_TEXTS:
        full_text = ARABIC_TEXTS[doi]
    
    return jsonify({
        "index": index,
        "doi": doi,
        "title": p.get("title", ""),
        "year": p.get("year"),
        "authors": p.get("authors", ""),
        "keywords": p.get("keywords", []),
        "has_pdf": bool(p.get("has_pdf")),
        "full_text": full_text,
        "abstract": p.get("abstract", ""),
    })

@app.route('/api/save', methods=['POST'])
def save_verification():
    """保存验证结果"""
    data = request.json
    index = data.get('index')
    tourism_class = data.get('tourism_class')  # core/maybe/none
    is_arabic_content = data.get('is_arabic_content')  # 是否真正阿语正文
    is_china_arab_related = data.get('is_china_arab_related')  # 是否中阿相关
    notes = data.get('notes', '')
    
    if index is None or tourism_class is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    # 加载现有结果
    results = load_verification_results()
    
    # 更新结果
    p = ARABIC_PAPERS[index]
    results[str(index)] = {
        "doi": p.get("doi", ""),
        "title": p.get("title", ""),
        "year": p.get("year"),
        "tourism_class": tourism_class,
        "is_arabic_content": is_arabic_content,
        "is_china_arab_related": is_china_arab_related,
        "notes": notes,
        "verified_at": datetime.now().isoformat(),
    }
    
    # 保存
    save_verification_results(results)
    
    return jsonify({"success": True, "verified_count": len(results)})

@app.route('/api/results')
def get_results():
    """获取所有验证结果"""
    results = load_verification_results()
    
    # 统计
    stats = {
        "total": len(ARABIC_PAPERS),
        "verified": len(results),
        "core": sum(1 for r in results.values() if r.get("tourism_class") == "core"),
        "maybe": sum(1 for r in results.values() if r.get("tourism_class") == "maybe"),
        "none": sum(1 for r in results.values() if r.get("tourism_class") == "none"),
    }
    
    return jsonify({"results": results, "stats": stats})

# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("阿语文献人工验证工具")
    print("=" * 60)
    print(f"阿语文献总数: {len(ARABIC_PAPERS)}")
    print(f"启动服务器: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
