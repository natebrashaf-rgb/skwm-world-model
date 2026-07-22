#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  中阿文旅新闻会议 RSS 自动采集                                  ║
║                                                                ║
║  对应策划案第一层「数据资源层」: 新闻会议                       ║
║  输出: E:\\大挑\\01_literature\\news\\  (JSON+Markdown)           ║
║                                                                ║
║  用法: python news_collector.py                                 ║
╚══════════════════════════════════════════════════════════════════╝
"""
import json, os, re, time, hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from xml.etree import ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── 路径 ──────────────────────────────────────────────────────────
OUT_DIR = Path(r"E:\大挑\01_literature\_news")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OBSIDIAN_DIR = Path(r"E:\大挑\skwm_platform\backend\obsidian_vault\新闻会议")
OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)

# ── RSS 源 ────────────────────────────────────────────────────────
RSS_FEEDS = [
    # 中阿文旅相关 Google News RSS
    ("Google News 中阿文旅", "https://news.google.com/rss/search?q=中阿+文旅&hl=zh-CN&gl=CN"),
    ("Google News China-Arab", "https://news.google.com/rss/search?q=China+Arab+cultural+tourism&hl=en-US&gl=US"),
    ("Google News 一带一路文旅", "https://news.google.com/rss/search?q=一带一路+文旅&hl=zh-CN&gl=CN"),
    ("Google News Arab tourism China", "https://news.google.com/rss/search?q=Arab+tourism+China&hl=en-US&gl=US"),
    
    # 其他源（备用）
    ("Xinhua 中阿", "http://www.xinhuanet.com/english/rss/china_news.xml"),
]

CACHE_FILE = OUT_DIR / "_cache.json"
CACHE_TTL = 3600  # 1小时

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def fetch_rss(url: str, timeout: int = 15) -> List[Dict]:
    """抓取单个 RSS 源，返回条目列表"""
    items = []
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        # 尝试解析
        root = ET.fromstring(raw)
        ns = {"": "http://www.w3.org/2005/Atom"}
        
        # 尝试 RSS 2.0 格式
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title", ""))
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            desc = _clean(item.findtext("description", "")[:300])
            if title:
                items.append({
                    "title": title, "link": link,
                    "date": pub_date, "summary": desc,
                    "source": url,
                })
        
        # 尝试 Atom 格式
        if not items:
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                title = _clean(entry.findtext("{http://www.w3.org/2005/Atom}title", ""))
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.get("href", "") if link_el is not None else ""
                pub_date = entry.findtext("{http://www.w3.org/2005/Atom}published", "")
                desc = _clean(entry.findtext("{http://www.w3.org/2005/Atom}summary", "")[:300])
                if title:
                    items.append({
                        "title": title, "link": link,
                        "date": pub_date, "summary": desc,
                        "source": url,
                    })
    except Exception as e:
        print(f"  ⚠️ {url.split('/')[2]}: {e}")
    return items


def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)  # 去HTML标签
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text.strip()[:300]


def deduplicate(items: List[Dict]) -> List[Dict]:
    """基于标题去重"""
    seen = set()
    result = []
    for it in items:
        key = it["title"][:40].lower()
        if key not in seen:
            seen.add(key)
            result.append(it)
    return result


def load_cache() -> Dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except: pass
    return {"items": [], "updated": ""}


def save_cache(items: List[Dict]):
    CACHE_FILE.write_text(
        json.dumps({"items": items, "updated": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main():
    print("📡 新闻会议 RSS 采集器")
    print(f"  源数: {len(RSS_FEEDS)}")
    print(f"  输出: {OUT_DIR}/")
    print()
    
    cache = load_cache()
    old_count = len(cache["items"])
    
    all_items = []
    for name, url in RSS_FEEDS:
        print(f"  📡 {name}...", end=" ")
        items = fetch_rss(url)
        print(f"{len(items)} 条")
        all_items.extend(items)
        time.sleep(0.5)  # 礼貌间隔
    
    all_items = deduplicate(all_items)
    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    print(f"\n  📊 总计: {len(all_items)} 条（去重后）")
    if old_count > 0:
        new_items = [i for i in all_items if i["title"][:40].lower() not in 
                     {c["title"][:40].lower() for c in cache["items"]}]
        print(f"  🆕 新增: {len(new_items)} 条")
    
    # 保存 JSON
    fp = OUT_DIR / f"news_{datetime.now():%Y%m%d_%H%M}.json"
    fp.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ JSON: {fp}")
    
    # 更新缓存
    save_cache(all_items)
    
    # 保存最新的 Markdown 摘要到 Obsidian
    md_lines = [
        f"# 中阿文旅新闻会议 (自动采集)",
        f"> 采集时间: {datetime.now():%Y-%m-%d %H:%M}",
        f"> 来源: {len(RSS_FEEDS)} 个 RSS 源",
        f"> 条数: {len(all_items)}",
        "",
        "---",
        "",
    ]
    for i, item in enumerate(all_items[:30]):
        md_lines.append(f"### {i+1}. {item['title']}")
        md_lines.append(f"- **链接:** {item['link']}")
        md_lines.append(f"- **时间:** {item.get('date','未知')}")
        if item.get("summary"):
            md_lines.append(f"- **摘要:** {item['summary'][:200]}")
        md_lines.append("")
    
    md_fp = OBSIDIAN_DIR / f"新闻摘要_{datetime.now():%Y%m%d}.md"
    md_fp.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"  ✅ Obsidian: {md_fp}")
    
    # 展示 Top 5
    print(f"\n{'='*50}")
    print("📋 最新 5 条新闻")
    print(f"{'='*50}")
    for item in all_items[:5]:
        print(f"  📰 {item['title']}")
        print(f"     {item.get('date','')[:16]}")
        print()


if __name__ == "__main__":
    main()
