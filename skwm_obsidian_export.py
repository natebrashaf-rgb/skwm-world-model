#!/usr/bin/env python3
"""
SKWM → Obsidian 知识库自动导出管线
===================================
从 GraphRAG 审核通过的内容自动生成 Obsidian 笔记
"""
import os, json, hashlib, re, time
from pathlib import Path
from datetime import datetime
from typing import Optional

BASE = Path(__file__).parent
VAULT_DIR = BASE / "output" / "obsidian_vault"
SEDIMENT_DIR = BASE / "output" / "graphrag_evidence" / "sediment"
REVIEW_DB = BASE / "output" / "graphrag_evidence" / "qa_reviews.json"


def load_reviews() -> list:
    """加载已审核通过的问答"""
    if not REVIEW_DB.exists():
        return []
    raw = json.loads(REVIEW_DB.read_text(encoding="utf-8"))
    approved = []
    for qa_id, qa in raw.items():
        status = qa.get("review_status", "")
        if status in ("approved", "edited"):
            approved.append(qa)
    return approved


def sanitize_filename(text: str) -> str:
    """规范化文件名"""
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    return text.strip()[:50]


def export_qa(qa: dict) -> Optional[Path]:
    """将单条问答导出为 Obsidian 笔记"""
    question = qa.get("question", "未命名问答")[:40]
    qa_id = qa.get("qa_id", hashlib.md5(question.encode()).hexdigest()[:8])
    confidence = qa.get("overall_confidence", 0)
    sources = qa.get("sources", [])
    answer = qa.get("edited_answer", qa.get("answer", ""))
    reviewer = qa.get("reviewed_by", "系统")
    reviewed_at = qa.get("reviewed_at", time.time())
    comment = qa.get("review_comment", "")

    # 构建来源表格
    src_table = "\n".join(
        f"| {s.get('type','?')} | {s.get('id','')[:20]} | {s.get('title','')[:30]} | {s.get('confidence',0):.0%} |"
        for s in sources[:5]
    )

    # 提取热点/前沿/术语关键词（用于双链）
    related_hotspots = []
    related_terms = []
    for s in sources:
        title = s.get("title", "")
        if title and s.get("type") == "entity":
            related_terms.append(f"[[术语_{title}]]")
        elif title and s.get("type") == "community":
            related_hotspots.append(f"[[{title[:30]}]]")

    # 生成笔记
    date_str = datetime.fromtimestamp(reviewed_at).strftime("%Y-%m-%d")
    note = f"""---
type: qa
created: {date_str}
question: "{question}"
confidence: {confidence:.0%}
review_status: {'edited' if qa.get('edited_answer') else 'approved'}
reviewer: {reviewer}
model: deepseek
sources: {len(sources)}
aliases: ["QA-{qa_id}"]
tags: [qa, 问答, approved]
---

# Q: {question}

## 答案

{answer}

## 证据来源
| 类型 | ID | 标题 | 置信度 |
|------|-----|------|--------|
{src_table}

## 关联知识
{chr(10).join('- ' + h for h in related_hotspots[:3])}
{chr(10).join('- ' + t for t in related_terms[:5])}

## 审核记录
- 审核人: {reviewer}
- 审核时间: {date_str}
- 批注: {comment}

---
*本记录由 SKWM 自动导出管线生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    fname = f"QA_{question}_{qa_id[:6]}.md"
    path = VAULT_DIR / "问答" / fname
    path.write_text(note, encoding="utf-8")
    return path


def export_report(title: str, content: str, report_type: str = "热点") -> Optional[Path]:
    """导出报告到对应目录"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    fname = f"{date_str}_{sanitize_filename(title)}.md"
    dir_path = VAULT_DIR / report_type
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / fname
    note = f"""---
type: {report_type}
created: {date_str}
title: "{title}"
source: skwm-auto-export
tags: [{report_type}, auto-export]
---

# {title}

{content}

---
*由 SKWM 自动导出 · {date_str}*
"""
    path.write_text(note, encoding="utf-8")
    return path


def main():
    print("=" * 60)
    print("  SKWM → Obsidian 知识库自动导出管线")
    print("=" * 60)
    
    # 1. 导出审核通过的问答
    approved = load_reviews()
    print(f"\n📥 待导出问答: {len(approved)} 条")
    for qa in approved:
        path = export_qa(qa)
        if path:
            print(f"  ✅ {path.name}")
    
    # 2. 统计
    total = sum(len(files) for _, _, files in os.walk(VAULT_DIR) if files)
    print(f"\n📊 Obsidian 知识库总计: {total} 篇笔记")
    print(f"📁 位置: {VAULT_DIR}")
    
    # 3. 输出 vault 结构
    print("\n📂 目录结构:")
    for root, dirs, files in sorted(os.walk(VAULT_DIR)):
        if '.obsidian' in root:
            continue
        level = root.replace(str(VAULT_DIR), "").count(os.sep)
        indent = "  " * level
        print(f"{indent}{os.path.basename(root)}/")
        for f in sorted(files):
            if f.endswith(".md"):
                print(f"{indent}  {f}")
    
    print(f"\n🎉 导出完成，使用 Obsidian 打开 {VAULT_DIR} 即可查看")


if __name__ == "__main__":
    main()
