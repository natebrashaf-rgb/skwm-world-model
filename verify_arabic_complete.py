#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整验证阿语文献真实性
1. 重试失败的DOI
2. 对无DOI文献进行标题搜索
"""
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

def load_b1():
    raw = open("data/B1_文献主表.json", encoding='utf-8').read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)

def verify_doi_with_retry(doi, max_retries=3):
    """带重试的DOI验证"""
    url = f"https://api.crossref.org/works/{doi}"
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'SKWM-Verifier/1.0 (mailto:test@example.com)',
                'Accept': 'application/json'
            })
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get('status') == 'ok':
                    work = data['message']
                    title = work.get('title', [''])[0] if work.get('title') else ''
                    year = None
                    
                    # 尝试多个年份字段
                    for date_field in ['published-print', 'published-online', 'created']:
                        if date_field in work:
                            date_parts = work[date_field].get('date-parts', [[None]])[0]
                            if date_parts and date_parts[0]:
                                year = date_parts[0]
                                break
                    
                    return True, title, year, None
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, None, None, "DOI不存在(404)"
            else:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return False, None, None, f"HTTP错误: {e.code}"
        
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return False, None, None, f"错误: {str(e)}"
    
    return False, None, None, "重试失败"

def search_title_openalex(title):
    """使用OpenAlex搜索标题"""
    # 清理标题
    clean_title = title[:100]  # 取前100字符
    encoded_title = urllib.parse.quote(clean_title)
    url = f"https://api.openalex.org/works?search={encoded_title}&per_page=1"
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SKWM-Verifier/1.0',
            'Accept': 'application/json'
        })
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            results = data.get('results', [])
            if results:
                work = results[0]
                return {
                    "found": True,
                    "title": work.get('title', ''),
                    "year": work.get('publication_year'),
                    "doi": work.get('doi', '').replace('https://doi.org/', '') if work.get('doi') else None,
                    "relevance": work.get('relevance_score', 0)
                }
            else:
                return {"found": False}
    
    except Exception as e:
        return {"found": False, "error": str(e)}

def main():
    b1 = load_b1()
    arabic = [p for p in b1 if p.get("language") == "ar"]
    
    print("=" * 80)
    print("阿语文献完整性验证")
    print("=" * 80)
    
    # 加载之前的验证结果
    prev_results = json.load(open("output/doi_verification_results.json", encoding='utf-8'))
    
    final_results = {
        "verified": [],      # 已验证真实存在
        "not_found": [],     # 未找到
        "no_doi_found": [],  # 无DOI但通过标题找到
        "no_doi_not_found": [],  # 无DOI且未找到
        "uncertain": []      # 不确定
    }
    
    # 1. 处理已验证成功的DOI
    print("\n[1] 已验证成功的DOI")
    for r in prev_results["valid"]:
        final_results["verified"].append({
            "doi": r["doi"],
            "title": r["local_title"],
            "year": r.get("local_year") or r.get("crossref_year"),
            "source": "CrossRef",
            "status": "verified"
        })
    print(f"  ✓ {len(prev_results['valid'])}篇")
    
    # 2. 重试失败的DOI
    print("\n[2] 重试失败的DOI")
    for r in prev_results["invalid"]:
        doi = r["doi"]
        print(f"  重试: {doi}")
        
        exists, title, year, error = verify_doi_with_retry(doi)
        
        if exists:
            print(f"    ✓ 验证成功")
            final_results["verified"].append({
                "doi": doi,
                "title": r["local_title"],
                "year": r.get("local_year") or year,
                "source": "CrossRef (重试成功)",
                "status": "verified"
            })
        else:
            print(f"    ✗ 仍然失败: {error}")
            if "404" in error:
                final_results["not_found"].append({
                    "doi": doi,
                    "title": r["local_title"],
                    "year": r.get("local_year"),
                    "error": error,
                    "status": "doi_not_found"
                })
            else:
                final_results["uncertain"].append({
                    "doi": doi,
                    "title": r["local_title"],
                    "year": r.get("local_year"),
                    "error": error,
                    "status": "uncertain"
                })
        
        time.sleep(1)
    
    # 3. 对无DOI的文献进行标题搜索
    print("\n[3] 无DOI文献的标题搜索")
    for r in prev_results["no_doi"]:
        title = r["title"]
        year = r.get("year")
        
        print(f"  搜索: {title[:50]}...")
        
        result = search_title_openalex(title)
        
        if result.get("found"):
            relevance = result.get("relevance", 0)
            print(f"    ✓ 找到 (相关度: {relevance:.2f})")
            print(f"      标题: {result['title'][:50]}...")
            
            # 判断是否足够相关
            if relevance > 0.5:
                final_results["no_doi_found"].append({
                    "title": title,
                    "year": year,
                    "found_title": result["title"],
                    "found_year": result.get("year"),
                    "found_doi": result.get("doi"),
                    "relevance": relevance,
                    "status": "found_by_title"
                })
            else:
                final_results["uncertain"].append({
                    "title": title,
                    "year": year,
                    "found_title": result["title"],
                    "relevance": relevance,
                    "status": "low_relevance"
                })
        else:
            print(f"    ✗ 未找到")
            final_results["no_doi_not_found"].append({
                "title": title,
                "year": year,
                "status": "not_found"
            })
        
        time.sleep(0.5)
    
    # 4. 输出统计
    print("\n" + "=" * 80)
    print("最终验证结果")
    print("=" * 80)
    print(f"✓ 已验证真实存在: {len(final_results['verified'])}篇")
    print(f"✗ DOI不存在: {len(final_results['not_found'])}篇")
    print(f"? 无DOI但通过标题找到: {len(final_results['no_doi_found'])}篇")
    print(f"? 无DOI且未找到: {len(final_results['no_doi_not_found'])}篇")
    print(f"? 不确定: {len(final_results['uncertain'])}篇")
    
    # 计算可信度
    total = len(arabic)
    verified = len(final_results['verified']) + len(final_results['no_doi_found'])
    print(f"\n可信度: {verified}/{total} = {verified/total*100:.1f}%")
    
    # 5. 保存结果
    output_path = Path("output/arabic_papers_verification.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total,
                "verified": len(final_results['verified']),
                "not_found": len(final_results['not_found']),
                "no_doi_found": len(final_results['no_doi_found']),
                "no_doi_not_found": len(final_results['no_doi_not_found']),
                "uncertain": len(final_results['uncertain']),
                "credibility": f"{verified/total*100:.1f}%"
            },
            "details": final_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到: {output_path}")
    
    # 6. 输出问题文献
    if final_results["not_found"]:
        print("\n" + "=" * 80)
        print("DOI不存在的文献")
        print("=" * 80)
        for r in final_results["not_found"]:
            print(f"  DOI: {r['doi']}")
            print(f"  标题: {r['title'][:60]}...")
            print()
    
    if final_results["no_doi_not_found"]:
        print("=" * 80)
        print("无DOI且未找到的文献")
        print("=" * 80)
        for r in final_results["no_doi_not_found"]:
            print(f"  标题: {r['title'][:60]}...")
            print(f"  年份: {r.get('year', '未知')}")
            print()

if __name__ == "__main__":
    main()
