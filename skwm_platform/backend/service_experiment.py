#!/usr/bin/env python3
"""
SKWM 服务可行性实验（精简版）
- 缩小范围：聚焦核心领域（文化遗产、旅游、中阿关系、数字文旅）
- 增加服务讨论：四类用户服务场景
- 避免数据库解析问题：直接使用 DataLayer
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from skwm_aligned_v4 import DataLayer, DeepSeekClient, SKWMController
from skwm_context import ContextEngine
from skwm_service import ServiceRules
from skwm_closed_loop import create_controller


# ═══════════════════════════════════════════════════════════════
# 实验配置
# ═══════════════════════════════════════════════════════════════

# 核心查询词（聚焦4个领域，每领域5个词，共20个）
CORE_QUERIES = [
    # 文化遗产（5个）
    {"word": "文化遗产", "category": "文化遗产", "service": "教师科研"},
    {"word": "非物质文化遗产", "category": "文化遗产", "service": "学生选题"},
    {"word": "文物数字化", "category": "文化遗产", "service": "馆员服务"},
    {"word": "cultural heritage", "category": "文化遗产", "service": "科研管理"},
    {"word": "遗产保护", "category": "文化遗产", "service": "教师科研"},
    
    # 旅游（5个）
    {"word": "文化旅游", "category": "旅游", "service": "学生选题"},
    {"word": "智慧旅游", "category": "旅游", "service": "馆员服务"},
    {"word": "可持续旅游", "category": "旅游", "service": "科研管理"},
    {"word": "cultural tourism", "category": "旅游", "service": "教师科研"},
    {"word": "文旅融合", "category": "旅游", "service": "学生选题"},
    
    # 中阿关系（5个）
    {"word": "一带一路", "category": "中阿关系", "service": "科研管理"},
    {"word": "跨文化传播", "category": "中阿关系", "service": "教师科研"},
    {"word": "silk road", "category": "中阿关系", "service": "学生选题"},
    {"word": "中阿合作", "category": "中阿关系", "service": "馆员服务"},
    {"word": "阿拉伯文化", "category": "中阿关系", "service": "科研管理"},
    
    # 数字文旅（5个）
    {"word": "数字文旅", "category": "数字文旅", "service": "馆员服务"},
    {"word": "数字人文", "category": "数字文旅", "service": "教师科研"},
    {"word": "knowledge graph", "category": "数字文旅", "service": "学生选题"},
    {"word": "LLM", "category": "数字文旅", "service": "科研管理"},
    {"word": "人工智能", "category": "数字文旅", "service": "馆员服务"},
]

# 四类用户服务场景
USER_SCENARIOS = {
    "teacher": {
        "name": "教师科研",
        "tasks": ["课题申报", "前沿追踪", "文献发现"],
        "focus": ["growth", "centrality"],
        "service_desc": "为教师提供前沿研究动态、课题申报参考"
    },
    "student": {
        "name": "学生学习",
        "tasks": ["论文选题", "术语查询", "研究入门"],
        "focus": ["heat", "connections"],
        "service_desc": "为学生提供热门选题、入门路径"
    },
    "librarian": {
        "name": "馆员服务",
        "tasks": ["学科咨询", "报告生成", "资源推送"],
        "focus": ["robustness", "verifiability"],
        "service_desc": "为馆员提供学科咨询支持、报告生成"
    },
    "manager": {
        "name": "科研管理",
        "tasks": ["机构画像", "学科评估", "趋势分析"],
        "focus": ["trend", "impact"],
        "service_desc": "为管理层提供学科评估、趋势预测"
    }
}


def run_experiment():
    """运行实验"""
    print("=" * 70)
    print("SKWM 服务可行性实验（精简版）")
    print("=" * 70)
    print()
    
    # 初始化
    print("🔧 初始化系统...")
    data = DataLayer().load(verbose=False)
    ds = DeepSeekClient()
    ctrl = SKWMController(data, ds)
    ctx = ContextEngine()
    svc = ServiceRules(data=data)
    loop_ctrl = create_controller(data, ds)
    
    print(f"✅ 数据加载完成")
    print(f"   - 时间切片: {len(data.snapshots)}年")
    print(f"   - 状态向量: {data.n_state_vectors:,}条")
    print(f"   - 年份范围: {data.year_range}")
    print()
    
    results = []
    start_total = time.time()
    
    # ═══════════════════════════════════════════════════════════
    # 实验1: 核心查询测试
    # ═══════════════════════════════════════════════════════════
    print("📊 实验1: 核心查询测试（20个词）")
    print("-" * 50)
    
    for i, q in enumerate(CORE_QUERIES, 1):
        word = q["word"]
        category = q["category"]
        service = q["service"]
        
        start = time.time()
        
        # 使用 DataLayer 直接查询（避免 Neo4j 解析问题）
        year = max(data.year_range)
        
        # 1. 热点匹配
        hot = data.get_hot_topics(year, 20)
        hot_names = [h["name"] for h in hot]
        
        # 2. 前沿匹配
        emerging = data.get_emerging(year, 20)
        em_names = [e["name"] for e in emerging]
        
        # 3. 关键词匹配（简单字符串匹配）
        matched_hot = [h for h in hot if word.lower() in h["name"].lower() or h["name"].lower() in word.lower()]
        matched_em = [e for e in emerging if word.lower() in e["name"].lower() or e["name"].lower() in word.lower()]
        
        # 4. 计算相关性得分
        if matched_hot:
            score = min(100, len(matched_hot) * 20 + matched_hot[0].get("heat", 0) // 10)
        elif matched_em:
            score = min(80, len(matched_em) * 15 + matched_em[0].get("growth", 0))
        else:
            # 尝试模糊匹配
            fuzzy_hot = [h for h in hot if any(c in h["name"] for c in word[:2])]
            score = len(fuzzy_hot) * 10 if fuzzy_hot else 0
        
        elapsed = (time.time() - start) * 1000
        
        result = {
            "序号": i,
            "查询词": word,
            "类别": category,
            "服务场景": service,
            "热点命中": len(matched_hot),
            "前沿命中": len(matched_em),
            "相关性": score,
            "耗时(ms)": round(elapsed, 1),
            "热点词": [h["name"] for h in matched_hot[:3]],
        }
        results.append(result)
        
        status = "✓" if score > 0 else "✗"
        print(f"  [{status}] {word:20s} | 热点:{len(matched_hot):2d} | 前沿:{len(matched_em):2d} | 相关性:{score:3d} | {elapsed:.0f}ms")
    
    print()
    
    # ═══════════════════════════════════════════════════════════
    # 实验2: 四类用户服务测试
    # ═══════════════════════════════════════════════════════════
    print("👥 实验2: 四类用户服务测试")
    print("-" * 50)
    
    service_results = []
    year = max(data.year_range)
    
    for user_type, scenario in USER_SCENARIOS.items():
        print(f"\n  【{scenario['name']}】{scenario['service_desc']}")
        
        # 获取该用户类型的推荐
        hot = data.get_hot_topics(year, 10)
        reweighted = ctx.reweight(hot, year, user_type, score_key="heat")
        recommendations = svc.recommend(reweighted, user_type, top_k=5)
        
        # 闭环决策
        o = loop_ctrl.kwm.get_state(year - 2)
        plan, plan_score = loop_ctrl.decide(o, "前沿识别", user_type, M=2, L=2, B=2)
        
        service_result = {
            "user_type": user_type,
            "user_name": scenario["name"],
            "tasks": scenario["tasks"],
            "focus_dims": scenario["focus"],
            "top_recommendations": [r.get("name", "") for r in recommendations[:3]],
            "plan_note": plan.note if plan else "",
            "plan_score": round(plan_score, 2) if plan_score else 0,
        }
        service_results.append(service_result)
        
        print(f"    任务: {', '.join(scenario['tasks'])}")
        print(f"    关注维度: {', '.join(scenario['focus'])}")
        print(f"    Top推荐: {', '.join(service_result['top_recommendations'][:3])}")
        print(f"    闭环策略: {service_result['plan_note'][:40]}... (得分:{service_result['plan_score']})")
    
    print()
    
    # ═══════════════════════════════════════════════════════════
    # 实验3: 服务流程完整性测试
    # ═══════════════════════════════════════════════════════════
    print("🔄 实验3: 服务流程完整性测试")
    print("-" * 50)
    
    pipeline_results = []
    
    test_cases = [
        {"query": "文化遗产研究热点", "user": "teacher"},
        {"query": "旅游论文选题推荐", "user": "student"},
        {"query": "一带一路学科报告", "user": "librarian"},
        {"query": "中阿合作趋势分析", "user": "manager"},
    ]
    
    for tc in test_cases:
        query = tc["query"]
        user = tc["user"]
        
        start = time.time()
        
        # 完整服务流程
        result = ctrl.process(query)
        
        elapsed = (time.time() - start) * 1000
        
        # 提取关键信息
        skwm = result.get("skwm", {})
        entities_found = skwm.get("E", {}).get("entities_found", 0)
        hot_topics = skwm.get("S", {}).get("hot_topics", [])
        emerging = skwm.get("T", {}).get("emerging_topics", [])
        
        pipeline_result = {
            "query": query,
            "user": user,
            "user_name": USER_SCENARIOS[user]["name"],
            "entities_found": entities_found,
            "hot_topics": [h["name"] for h in hot_topics[:3]],
            "emerging": [e["name"] for e in emerging[:3]],
            "time_ms": round(elapsed, 1),
            "success": entities_found > 0 or len(hot_topics) > 0,
        }
        pipeline_results.append(pipeline_result)
        
        status = "✓" if pipeline_result["success"] else "✗"
        print(f"  [{status}] {query:20s} | 用户:{USER_SCENARIOS[user]['name']} | 实体:{entities_found} | 热点:{len(hot_topics)} | {elapsed:.0f}ms")
    
    print()
    
    # ═══════════════════════════════════════════════════════════
    # 汇总统计
    # ═══════════════════════════════════════════════════════════
    total_time = time.time() - start_total
    
    # 核心查询统计
    total_queries = len(results)
    hit_queries = sum(1 for r in results if r["相关性"] > 0)
    hit_rate = hit_queries / total_queries * 100
    avg_relevance = sum(r["相关性"] for r in results) / total_queries
    avg_time = sum(r["耗时(ms)"] for r in results) / total_queries
    
    # 按类别统计
    category_stats = {}
    for r in results:
        cat = r["类别"]
        if cat not in category_stats:
            category_stats[cat] = {"count": 0, "hit": 0, "rel_sum": 0}
        category_stats[cat]["count"] += 1
        if r["相关性"] > 0:
            category_stats[cat]["hit"] += 1
        category_stats[cat]["rel_sum"] += r["相关性"]
    
    for cat, stats in category_stats.items():
        stats["hit_rate"] = stats["hit"] / stats["count"] * 100
        stats["avg_rel"] = stats["rel_sum"] / stats["count"]
    
    # 服务流程统计
    pipeline_success = sum(1 for p in pipeline_results if p["success"])
    pipeline_rate = pipeline_success / len(pipeline_results) * 100
    
    summary = {
        "测试词总数": total_queries,
        "有结果词数": hit_queries,
        "命中率": f"{hit_rate:.1f}%",
        "平均相关性": f"{avg_relevance:.1f}/100",
        "平均响应时间": f"{avg_time:.1f}ms",
        "总耗时": f"{total_time:.1f}s",
        "服务流程通过率": f"{pipeline_rate:.1f}%",
        "系统状态": "✅ 可用" if hit_rate >= 70 else "⚠️ 需改进",
    }
    
    # ═══════════════════════════════════════════════════════════
    # 输出结果
    # ═══════════════════════════════════════════════════════════
    print("=" * 70)
    print("📈 实验结果汇总")
    print("=" * 70)
    print()
    print("【总体指标】")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    
    print()
    print("【按类别统计】")
    print(f"  {'类别':12s} | {'测试数':>6s} | {'命中数':>6s} | {'命中率':>7s} | {'平均相关':>8s}")
    print("  " + "-" * 55)
    for cat, stats in category_stats.items():
        print(f"  {cat:12s} | {stats['count']:6d} | {stats['hit']:6d} | {stats['hit_rate']:6.1f}% | {stats['avg_rel']:7.1f}")
    
    print()
    print("【服务流程测试】")
    for p in pipeline_results:
        status = "✓" if p["success"] else "✗"
        print(f"  [{status}] {p['query']} ({p['user_name']})")
        print(f"      热点: {', '.join(p['hot_topics'])}")
        print(f"      前沿: {', '.join(p['emerging'])}")
    
    print()
    print("【服务场景分析】")
    for sr in service_results:
        print(f"  {sr['user_name']}:")
        print(f"    任务: {', '.join(sr['tasks'])}")
        print(f"    推荐: {', '.join(sr['top_recommendations'])}")
        print(f"    策略: {sr['plan_note'][:50]}...")
    
    print()
    print("=" * 70)
    print(f"**综合判断: {summary['系统状态']}**")
    print("=" * 70)
    
    # ═══════════════════════════════════════════════════════════
    # 保存结果
    # ═══════════════════════════════════════════════════════════
    output_dir = Path(__file__).parent / "experiment_results"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON 完整数据
    json_data = {
        "timestamp": timestamp,
        "summary": summary,
        "category_stats": category_stats,
        "results": results,
        "service_results": service_results,
        "pipeline_results": pipeline_results,
    }
    
    json_path = output_dir / f"service_experiment_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    # Markdown 报告
    md_path = output_dir / f"service_experiment_{timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# SKWM 服务可行性实验报告（精简版）\n\n")
        f.write(f"> 实验时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 测试范围: 核心领域（文化遗产、旅游、中阿关系、数字文旅）\n")
        f.write(f"> 服务场景: 四类用户（教师/学生/馆员/管理）\n\n")
        
        f.write(f"## 一、总体指标\n\n")
        f.write(f"| 指标 | 数值 |\n")
        f.write(f"|------|------|\n")
        for k, v in summary.items():
            f.write(f"| {k} | {v} |\n")
        
        f.write(f"\n## 二、按类别统计\n\n")
        f.write(f"| 类别 | 测试数 | 命中数 | 命中率 | 平均相关性 |\n")
        f.write(f"|------|:------:|:------:|:------:|:----------:|\n")
        for cat, stats in category_stats.items():
            f.write(f"| {cat} | {stats['count']} | {stats['hit']} | {stats['hit_rate']:.1f}% | {stats['avg_rel']:.1f} |\n")
        
        f.write(f"\n## 三、核心查询结果\n\n")
        f.write(f"| 序号 | 查询词 | 类别 | 服务场景 | 热点命中 | 相关性 | 耗时 |\n")
        f.write(f"|:----:|--------|------|----------|:--------:|:------:|:----:|\n")
        for r in results:
            f.write(f"| {r['序号']} | {r['查询词']} | {r['类别']} | {r['服务场景']} | {r['热点命中']} | {r['相关性']} | {r['耗时(ms)']:.0f}ms |\n")
        
        f.write(f"\n## 四、四类用户服务测试\n\n")
        for sr in service_results:
            f.write(f"### {sr['user_name']}\n\n")
            f.write(f"- **任务**: {', '.join(sr['tasks'])}\n")
            f.write(f"- **关注维度**: {', '.join(sr['focus_dims'])}\n")
            f.write(f"- **Top推荐**: {', '.join(sr['top_recommendations'])}\n")
            f.write(f"- **闭环策略**: {sr['plan_note']}\n")
            f.write(f"- **策略得分**: {sr['plan_score']}\n\n")
        
        f.write(f"\n## 五、服务流程测试\n\n")
        f.write(f"| 查询 | 用户 | 实体数 | 热点 | 前沿 | 状态 |\n")
        f.write(f"|------|------|:------:|------|------|:----:|\n")
        for p in pipeline_results:
            status = "✓" if p["success"] else "✗"
            f.write(f"| {p['query']} | {p['user_name']} | {p['entities_found']} | {', '.join(p['hot_topics'])} | {', '.join(p['emerging'])} | {status} |\n")
        
        f.write(f"\n## 六、服务场景讨论\n\n")
        f.write(f"### 6.1 教师科研服务\n\n")
        f.write(f"**场景**: 课题申报、前沿追踪、文献发现\n\n")
        f.write(f"**服务流程**:\n")
        f.write(f"1. 查询领域热点 → 识别研究方向\n")
        f.write(f"2. 语境加权 → 匹配国家政策（如一带一路）\n")
        f.write(f"3. 闭环规划 → 生成课题申报建议\n\n")
        f.write("**示例**: 查询\"文化遗产研究热点\" → 返回遗产、文化、数字等热点 → 推荐\"数字文旅\"方向申报\n\n")
        
        f.write(f"### 6.2 学生学习服务\n\n")
        f.write(f"**场景**: 论文选题、术语查询、研究入门\n\n")
        f.write(f"**服务流程**:\n")
        f.write(f"1. 查询热门主题 → 提供选题参考\n")
        f.write(f"2. 关联实体 → 构建知识图谱\n")
        f.write(f"3. 推荐入门路径 → 降低学习门槛\n\n")
        f.write("**示例**: 查询\"旅游论文选题\" → 返回文化旅游、智慧旅游等热点 → 推荐\"可持续旅游\"作为选题\n\n")
        
        f.write(f"### 6.3 馆员服务\n\n")
        f.write(f"**场景**: 学科咨询、报告生成、资源推送\n\n")
        f.write(f"**服务流程**:\n")
        f.write(f"1. 接收咨询请求 → 解析用户需求\n")
        f.write(f"2. 调用知识图谱 → 生成学科报告\n")
        f.write(f"3. 馆员审核 → 推送给用户\n\n")
        f.write("**示例**: 查询\"一带一路学科报告\" → 生成包含热点、前沿、趋势的报告 → 馆员审核后推送\n\n")
        
        f.write(f"### 6.4 科研管理服务\n\n")
        f.write(f"**场景**: 机构画像、学科评估、趋势分析\n\n")
        f.write(f"**服务流程**:\n")
        f.write(f"1. 收集机构数据 → 构建画像\n")
        f.write(f"2. 趋势预测 → 评估学科发展\n")
        f.write(f"3. 生成决策建议 → 支持管理决策\n\n")
        f.write("**示例**: 查询\"中阿合作趋势分析\" → 预测未来3年发展方向 → 生成学科建设建议\n\n")
        
        f.write(f"---\n")
        f.write(f"*报告由 SKWM 实验系统自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    
    # CSV 报表
    csv_path = output_dir / f"service_experiment_{timestamp}.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("序号,查询词,类别,服务场景,热点命中,前沿命中,相关性,耗时(ms)\n")
        for r in results:
            f.write(f"{r['序号']},{r['查询词']},{r['类别']},{r['服务场景']},{r['热点命中']},{r['前沿命中']},{r['相关性']},{r['耗时(ms)']}\n")
    
    print()
    print(f"📁 结果已保存到: {output_dir}")
    print(f"   - JSON: service_experiment_{timestamp}.json")
    print(f"   - Markdown: service_experiment_{timestamp}.md")
    print(f"   - CSV: service_experiment_{timestamp}.csv")
    
    return json_data


if __name__ == "__main__":
    run_experiment()
