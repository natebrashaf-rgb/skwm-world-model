#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证阿语文献DOI的真实性
使用CrossRef API检查DOI是否真实注册
"""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

def load_b1():
    """加载B1文献主表"""
    raw = open("data/B1_文献主表.json", encoding='utf-8').read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)

def verify_doi_crossref(doi):
    """
    使用CrossRef API验证DOI
    返回: (存在, 标题, 年份, 错误信息)
    """
    url = f"https://api.crossref.org/works/{doi}"
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SKWM-DOI-Verifier/1.0 (mailto:test@example.com)'
        })
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('status') == 'ok':
                work = data['message']
                title = work.get('title', [''])[0] if work.get('title') else ''
                year = work.get('published-print', {}).get('date-parts', [[None]])[0][0]
                if not year:
                    year = work.get('published-online', {}).get('date-parts', [[None]])[0][0]
                
                return True, title, year, None
            else:
                return False, None, None, "API返回非ok状态"
    
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, None, None, "DOI不存在(404)"
        else:
            return False, None, None, f"HTTP错误: {e.code}"
    
    except urllib.error.URLError as e:
        return False, None, None, f"网络错误: {str(e.reason)}"
    
    except Exception as e:
        return False, None, None, f"未知错误: {str(e)}"

def main():
    # 加载数据
    b1 = load_b1()
    arabic = [p for p in b1 if p.get("language") == "ar"]
    
    print("=" * 80)
    print("阿语文献DOI真实性验证")
    print("=" * 80)
    print(f"\n总文献数: {len(arabic)}")
    
    # 分离有DOI和无DOI的文献
    with_doi = [p for p in arabic if p.get("doi")]
    without_doi = [p for p in arabic if not p.get("doi")]
    
    print(f"有DOI: {len(with_doi)}篇")
    print(f"无DOI: {len(without_doi)}篇")
    
    # 验证有DOI的文献
    print("\n" + "=" * 80)
    print("验证有DOI的文献")
    print("=" * 80)
    
    results = {
        "valid": [],
        "invalid": [],
        "no_doi": []
    }
    
    for i, p in enumerate(with_doi, 1):
        doi = p.get("doi")
        title = p.get("title", "")
        year = p.get("year", "")
        
        print(f"\n[{i}/{len(with_doi)}] 验证DOI: {doi}")
        print(f"  本地标题: {title[:50]}...")
        
        # 调用CrossRef API
        exists, cr_title, cr_year, error = verify_doi_crossref(doi)
        
        if exists:
            print(f"  ✓ DOI真实存在")
            print(f"  CrossRef标题: {cr_title[:50]}...")
            print(f"  CrossRef年份: {cr_year}")
            
            # 检查标题是否匹配
            title_match = False
            if cr_title and title:
                # 简单检查：前20个字符是否相同
                title_match = title[:20] in cr_title or cr_title[:20] in title
            
            results["valid"].append({
                "doi": doi,
                "local_title": title,
                "local_year": year,
                "crossref_title": cr_title,
                "crossref_year": cr_year,
                "title_match": title_match
            })
        else:
            print(f"  ✗ DOI不存在或验证失败")
            print(f"  错误: {error}")
            results["invalid"].append({
                "doi": doi,
                "local_title": title,
                "local_year": year,
                "error": error
            })
        
        # 避免请求过快
        time.sleep(1)
    
    # 记录无DOI的文献
    for p in without_doi:
        results["no_doi"].append({
            "title": p.get("title", ""),
            "year": p.get("year", "")
        })
    
    # 输出统计
    print("\n" + "=" * 80)
    print("验证结果统计")
    print("=" * 80)
    print(f"✓ DOI真实存在: {len(results['valid'])}篇")
    print(f"✗ DOI不存在/验证失败: {len(results['invalid'])}篇")
    print(f"- 无DOI: {len(results['no_doi'])}篇")
    
    # 检查标题匹配
    if results["valid"]:
        matched = sum(1 for r in results["valid"] if r["title_match"])
        print(f"\n标题匹配检查:")
        print(f"  标题匹配: {matched}篇")
        print(f"  标题不匹配: {len(results['valid']) - matched}篇")
    
    # 保存结果
    output_path = Path("output/doi_verification_results.json")
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到: {output_path}")
    
    # 输出问题文献
    if results["invalid"]:
        print("\n" + "=" * 80)
        print("问题文献（DOI不存在）")
        print("=" * 80)
        for r in results["invalid"]:
            print(f"\nDOI: {r['doi']}")
            print(f"  标题: {r['local_title'][:60]}...")
            print(f"  错误: {r['error']}")
    
    if results["valid"]:
        mismatched = [r for r in results["valid"] if not r["title_match"]]
        if mismatched:
            print("\n" + "=" * 80)
            print("标题不匹配的文献")
            print("=" * 80)
            for r in mismatched:
                print(f"\nDOI: {r['doi']}")
                print(f"  本地标题: {r['local_title'][:60]}...")
                print(f"  CrossRef标题: {r['crossref_title'][:60]}...")

if __name__ == "__main__":
    main()
