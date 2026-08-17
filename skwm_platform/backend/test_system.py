#!/usr/bin/env python3
"""
SKWM 系统可行性测试实验
20-30个测试用例，验证各模块功能
"""
import sys
import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from skwm_aligned_v4 import DataLayer, DeepSeekClient, SKWMController
from neo4j_client import Neo4jClient, Neo4jConfig
from skwm_closed_loop import create_controller, create_evaluator
from skwm_context import ContextEngine
from skwm_service import ServiceRules


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        print("🔧 初始化测试环境...")
        
        # 加载数据
        self.data = DataLayer().load(verbose=False)
        self.ds = DeepSeekClient()
        self.ctrl = SKWMController(self.data, self.ds)
        
        # Neo4j
        config = Neo4jConfig.from_env()
        self.neo4j = Neo4jClient(config)
        self.neo4j.connect()
        
        # 闭环控制器
        self.loop_ctrl = create_controller(self.data, self.ds)
        self.evaluator = create_evaluator(self.data)
        
        # 语境引擎
        self.ctx = ContextEngine()
        self.svc = ServiceRules(data=self.data)
        
        # 测试结果
        self.results = []
        self.test_keywords = [
            # 中阿文旅核心词 (15个)
            "旅游", "文化", "遗产", "数字文旅", "一带一路",
            "中阿合作", "人工智能", "可持续发展", "博物馆", "非遗",
            "智慧旅游", "元宇宙", "跨文化传播", "区域国别", "文明交流",
            
            # 扩展领域 (15个)
            "文化遗产", "数字化", "旅游管理", "阿拉伯", "沙特",
            "阿联酋", "埃及", "卡塔尔", "知识图谱", "大数据",
            "机器学习", "深度学习", "教育", "健康", "政策",
            
            # 前沿词汇 (10个)
            "3D Cultural Heritage", "Digital Twin", "Virtual Reality",
            "Sustainable Tourism", "Cultural Exchange", "Belt and Road",
            "Middle East", "Gulf Countries", "Smart City", "Innovation"
        ]
        
        print(f"✅ 初始化完成，测试关键词: {len(self.test_keywords)}个\n")
    
    def run_test(self, test_id: int, name: str, func, **kwargs) -> Dict:
        """运行单个测试"""
        print(f"  [{test_id:02d}] {name}...", end=" ")
        start = time.time()
        
        try:
            result = func(**kwargs)
            elapsed = time.time() - start
            status = "✅" if result.get("success", True) else "❌"
            print(f"{status} ({elapsed:.2f}s)")
            
            test_result = {
                "id": test_id,
                "name": name,
                "status": "PASS" if result.get("success", True) else "FAIL",
                "time": round(elapsed, 3),
                "result": result,
            }
            self.results.append(test_result)
            return test_result
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"❌ 错误: {str(e)[:50]}")
            test_result = {
                "id": test_id,
                "name": name,
                "status": "ERROR",
                "time": round(elapsed, 3),
                "error": str(e),
            }
            self.results.append(test_result)
            return test_result
    
    # ═══════════════════════════════════════════════════════════════
    # 测试用例
    # ═══════════════════════════════════════════════════════════════
    
    def test_data_layer(self):
        """测试1: 数据层加载"""
        return {
            "success": True,
            "snapshots": len(self.data.snapshots),
            "state_vectors": self.data.n_state_vectors,
            "year_range": self.data.year_range,
        }
    
    def test_neo4j_connection(self):
        """测试2: Neo4j连接"""
        stats = self.neo4j.stats()
        return {
            "success": self.neo4j.connected,
            "nodes": sum(n["count"] for n in stats["nodes"]),
            "edges": sum(e["count"] for e in stats["edges"]),
        }
    
    def test_hotspot_analysis(self):
        """测试3: 热点分析"""
        year = max(self.data.year_range)
        hot = self.data.get_hot_topics(year, 10)
        return {
            "success": len(hot) > 0,
            "year": year,
            "top3": [h["name"] for h in hot[:3]],
            "count": len(hot),
        }
    
    def test_frontier_detection(self):
        """测试4: 前沿识别"""
        year = max(self.data.year_range)
        em = self.data.get_emerging(year, 10)
        return {
            "success": len(em) > 0,
            "year": year,
            "top3": [e["name"] for e in em[:3]],
            "count": len(em),
        }
    
    def test_predict_future(self):
        """测试5: 趋势预测"""
        year = max(self.data.year_range) - 3
        pred = self.data.predict_future(year, 3)
        return {
            "success": len(pred) > 0,
            "from_year": year,
            "to_year": year + 3,
            "top3": [p["name"] for p in pred[:3]],
        }
    
    def test_counterfactual(self):
        """测试6: 反事实分析"""
        year = max(self.data.year_range)
        hot = self.data.get_hot_topics(year, 1)
        if not hot:
            return {"success": False, "error": "无热点数据"}
        
        bridge = hot[0]["name"]
        cf = self.data.counterfactual(bridge, year)
        return {
            "success": cf.get("found", False),
            "bridge": bridge,
            "influence": cf.get("influence", 0),
            "level": cf.get("level", ""),
        }
    
    def test_neo4j_search(self):
        """测试7: Neo4j搜索"""
        keyword = random.choice(self.test_keywords[:10])
        results = self.neo4j.search(keyword, limit=10)
        return {
            "success": len(results) > 0,
            "keyword": keyword,
            "count": len(results),
            "sample": results[0] if results else None,
        }
    
    def test_neo4j_neighbors(self):
        """测试8: Neo4j邻居查询"""
        # 先找一个存在的节点
        nodes = self.neo4j.execute_cypher("MATCH (n) RETURN n.id AS id LIMIT 1")
        if not nodes:
            return {"success": False, "error": "无节点"}
        
        node_id = nodes[0]["id"]
        neighbors = self.neo4j.get_neighbors(node_id, depth=1)
        return {
            "success": len(neighbors.get("nodes", [])) > 0,
            "center": node_id,
            "neighbor_count": len(neighbors.get("nodes", [])),
        }
    
    def test_neo4j_collaboration(self):
        """测试9: 作者合作网络"""
        # 找一个真实作者
        authors = self.neo4j.execute_cypher("MATCH (a:Author) RETURN a.name AS name LIMIT 1")
        if not authors:
            return {"success": False, "error": "无作者"}
        
        author = authors[0]["name"]
        collab = self.neo4j.get_collaboration_network(author, limit=5)
        return {
            "success": True,
            "author": author,
            "collaborators": len(collab),
        }
    
    def test_neo4j_cooccur(self):
        """测试10: 共现关键词"""
        topics = self.neo4j.execute_cypher("MATCH (t:Topic) RETURN t.name AS name LIMIT 1")
        if not topics:
            return {"success": False, "error": "无主题"}
        
        topic = topics[0]["name"]
        cooccur = self.neo4j.get_co_occur_keywords(topic, limit=5)
        return {
            "success": True,
            "topic": topic,
            "cooccur_count": len(cooccur),
        }
    
    def test_context_engine(self):
        """测试11: 语境引擎"""
        year = max(self.data.year_range)
        hot = self.data.get_hot_topics(year, 5)
        reweighted = self.ctx.reweight(hot, year, "teacher", score_key="heat")
        return {
            "success": len(reweighted) > 0,
            "original_top": hot[0]["name"] if hot else "",
            "reweighted_top": reweighted[0]["name"] if reweighted else "",
            "changed": hot[0]["name"] != reweighted[0]["name"] if hot and reweighted else False,
        }
    
    def test_service_rules(self):
        """测试12: 服务规则"""
        year = max(self.data.year_range)
        hot = self.data.get_hot_topics(year, 5)
        recommendations = self.svc.recommend(hot, "teacher", top_k=3)
        return {
            "success": len(recommendations) > 0,
            "user": "teacher",
            "recommendations": len(recommendations),
        }
    
    def test_closed_loop_decide(self):
        """测试13: 闭环决策"""
        year = max(self.data.year_range) - 2
        o = self.loop_ctrl.kwm.get_state(year)
        plan, score = self.loop_ctrl.decide(o, "前沿识别", "student", M=2, L=2, B=2)
        return {
            "success": plan is not None,
            "year": year,
            "score": round(score, 3) if score else 0,
            "plan_note": plan.note if plan else "",
        }
    
    def test_closed_loop_run(self):
        """测试14: 跨年闭环规划"""
        decisions = self.loop_ctrl.run(2020, 2022, "中阿文旅", "teacher", M=2, L=2, B=2)
        return {
            "success": len(decisions) == 3,
            "years": [d["year"] for d in decisions],
            "avg_score": round(np.mean([d["score"] for d in decisions]), 3),
        }
    
    def test_evaluator_hit_rate(self):
        """测试15: 闭环评测-命中率"""
        result = self.evaluator.hit_rate(
            self.loop_ctrl, [2018, 2019], "student", L=2, k=5
        )
        return {
            "success": "avg_hit_rate" in result,
            "hit_rate": round(result.get("avg_hit_rate", 0), 3),
            "eval_years": [2018, 2019],
        }
    
    def test_keyword_batch_search(self):
        """测试16: 批量关键词搜索"""
        keywords = random.sample(self.test_keywords, 10)
        results = []
        for kw in keywords:
            res = self.neo4j.search(kw, limit=5)
            results.append({"keyword": kw, "count": len(res)})
        
        total = sum(r["count"] for r in results)
        return {
            "success": total > 0,
            "keywords_tested": len(keywords),
            "total_results": total,
            "avg_per_keyword": round(total / len(keywords), 2),
        }
    
    def test_hotspot_probability(self):
        """测试17: 热点概率计算"""
        year = max(self.data.year_range)
        hot = self.data.get_hot_topics(year, 20)
        
        if not hot:
            return {"success": False, "error": "无热点数据"}
        
        # 计算热度分布
        heats = [h["heat"] for h in hot]
        total_heat = sum(heats)
        probs = [h / total_heat for h in heats] if total_heat > 0 else [0] * len(heats)
        
        return {
            "success": True,
            "top_keyword": hot[0]["name"],
            "top_heat": round(heats[0], 3),
            "top_probability": round(probs[0], 4),
            "entropy": round(-sum(p * np.log(p + 1e-10) for p in probs), 3),
        }
    
    def test_growth_correlation(self):
        """测试18: 增速相关性分析"""
        year = max(self.data.year_range)
        entities = self.data.get_entities(year)
        
        if len(entities) < 5:
            return {"success": False, "error": "数据不足"}
        
        # 提取热度和增速
        data = []
        for name, vec in entities.items():
            if isinstance(vec, (list, tuple)) and len(vec) >= 2:
                data.append((vec[0], vec[1]))  # heat, growth
        
        if len(data) < 5:
            return {"success": False, "error": "有效数据不足"}
        
        heats = [d[0] for d in data]
        growths = [d[1] for d in data]
        
        # 计算相关系数
        corr = np.corrcoef(heats, growths)[0, 1] if len(data) > 1 else 0
        
        return {
            "success": True,
            "sample_size": len(data),
            "correlation": round(corr, 4),
            "interpretation": "正相关" if corr > 0.3 else "负相关" if corr < -0.3 else "弱相关",
        }
    
    def test_temporal_trend(self):
        """测试19: 时间趋势分析"""
        years = sorted([int(y) for y in self.data.snapshots.keys() if y.isdigit()])
        if len(years) < 5:
            return {"success": False, "error": "年份不足"}
        
        # 取最近5年
        recent_years = years[-5:]
        trends = []
        for y in recent_years:
            snap = self.data.snapshots.get(str(y), {})
            trends.append({
                "year": y,
                "nodes": snap.get("n_nodes", 0),
                "edges": snap.get("n_edges", 0),
            })
        
        # 计算趋势
        nodes = [t["nodes"] for t in trends]
        growth_rate = (nodes[-1] - nodes[0]) / nodes[0] if nodes[0] > 0 else 0
        
        return {
            "success": True,
            "years": recent_years,
            "start_nodes": nodes[0],
            "end_nodes": nodes[-1],
            "growth_rate": round(growth_rate, 4),
        }
    
    def test_entity_type_distribution(self):
        """测试20: 实体类型分布"""
        stats = self.neo4j.stats()
        node_stats = stats.get("nodes", [])
        
        return {
            "success": len(node_stats) > 0,
            "types": len(node_stats),
            "distribution": {n["labels"][0]: n["count"] for n in node_stats if n["labels"]},
        }
    
    def test_relation_type_distribution(self):
        """测试21: 关系类型分布"""
        stats = self.neo4j.stats()
        edge_stats = stats.get("edges", [])
        
        return {
            "success": len(edge_stats) > 0,
            "types": len(edge_stats),
            "distribution": {e["type"]: e["count"] for e in edge_stats},
        }
    
    def test_llm_fallback(self):
        """测试22: LLM降级测试"""
        # 测试无API Key时的降级
        ds_no_key = DeepSeekClient(api_key="invalid")
        result = ds_no_key.chat([{"role": "user", "content": "测试"}])
        return {
            "success": result == "规则降级响应（API不可用）",
            "response": result,
        }
    
    def test_arabic_agent(self):
        """测试23: 阿文智能体"""
        from skwm_aligned_v4 import ArabicAgent
        ar = ArabicAgent()
        
        if not ar.loaded:
            return {"success": False, "error": "术语表未加载"}
        
        # 检测阿拉伯语
        test_text = "السياحة الثقافية"
        detect = ar.detect_arabic(test_text)
        
        return {
            "success": detect.get("has_arabic", False),
            "text": test_text,
            "arabic_ratio": round(detect.get("arabic_ratio", 0), 4),
        }
    
    def test_graph_visualization_data(self):
        """测试24: 图谱可视化数据"""
        year = max(self.data.year_range)
        snapshot = self.data.snapshots.get(str(year), {})
        
        nodes = snapshot.get("nodes", [])[:50]
        edges = snapshot.get("edges", [])[:100]
        
        return {
            "success": len(nodes) > 0,
            "year": year,
            "nodes_count": len(nodes),
            "edges_count": len(edges),
        }
    
    def test_report_generation(self):
        """测试25: 报告生成"""
        year = max(self.data.year_range)
        report = self.ctrl.report.generate_report("中阿文旅", "teacher", year)
        
        return {
            "success": "title" in report,
            "title": report.get("title", ""),
            "sections": len(report.get("sections", [])),
        }
    
    def test_multi_hop_reasoning(self):
        """测试26: 多跳推理"""
        year = max(self.data.year_range)
        result = self.ctrl.literature.multi_hop("旅游", year)
        
        return {
            "success": len(result.get("related", [])) > 0,
            "source": "旅游",
            "related_count": len(result.get("related", [])),
            "hops": result.get("hops", 0),
        }
    
    def test_institution_profiles(self):
        """测试27: 机构画像"""
        inst_count = len(self.data._institutions)
        
        if inst_count == 0:
            return {"success": False, "error": "无机构数据"}
        
        # 取Top 5
        top_inst = sorted(
            self.data._institutions.items(),
            key=lambda x: x[1]["heat"],
            reverse=True
        )[:5]
        
        return {
            "success": True,
            "total_institutions": inst_count,
            "top5": [{"name": name, "heat": info["heat"]} for name, info in top_inst],
        }
    
    def test_author_profiles(self):
        """测试28: 作者画像"""
        author_count = len(self.data._authors)
        
        if author_count == 0:
            return {"success": False, "error": "无作者数据"}
        
        # 取Top 5
        top_authors = sorted(
            self.data._authors.items(),
            key=lambda x: x[1]["collab_count"],
            reverse=True
        )[:5]
        
        return {
            "success": True,
            "total_authors": author_count,
            "top5": [{"name": name, "collabs": info["collab_count"]} for name, info in top_authors],
        }
    
    def test_scaling_experiment(self):
        """测试29: 推理期缩放实验"""
        year = max(self.data.year_range) - 2
        o = self.loop_ctrl.kwm.get_state(year)
        
        results = []
        for M in [1, 2, 3]:
            plan, score = self.loop_ctrl.decide(o, "前沿识别", "teacher", M=M, L=2, B=2)
            results.append({"M": M, "score": round(score, 3) if score else 0})
        
        # 检查是否单调递增
        scores = [r["score"] for r in results]
        monotonic = all(scores[i] <= scores[i+1] for i in range(len(scores)-1))
        
        return {
            "success": True,
            "results": results,
            "monotonic_increase": monotonic,
        }
    
    def test_full_pipeline(self):
        """测试30: 完整服务流程"""
        query = "中阿文旅研究热点"
        user = "teacher"
        
        result = self.ctrl.process(query)
        
        return {
            "success": "skwm" in result,
            "query": query,
            "user": user,
            "entities_found": result.get("skwm", {}).get("E", {}).get("entities_found", 0),
        }
    
    def run_all(self):
        """运行所有测试"""
        print("=" * 60)
        print("SKWM 系统可行性测试")
        print("=" * 60)
        print()
        
        tests = [
            (1, "数据层加载", self.test_data_layer),
            (2, "Neo4j连接", self.test_neo4j_connection),
            (3, "热点分析", self.test_hotspot_analysis),
            (4, "前沿识别", self.test_frontier_detection),
            (5, "趋势预测", self.test_predict_future),
            (6, "反事实分析", self.test_counterfactual),
            (7, "Neo4j搜索", self.test_neo4j_search),
            (8, "Neo4j邻居", self.test_neo4j_neighbors),
            (9, "作者合作网络", self.test_neo4j_collaboration),
            (10, "共现关键词", self.test_neo4j_cooccur),
            (11, "语境引擎", self.test_context_engine),
            (12, "服务规则", self.test_service_rules),
            (13, "闭环决策", self.test_closed_loop_decide),
            (14, "跨年规划", self.test_closed_loop_run),
            (15, "闭环评测", self.test_evaluator_hit_rate),
            (16, "批量搜索", self.test_keyword_batch_search),
            (17, "热点概率", self.test_hotspot_probability),
            (18, "增速相关性", self.test_growth_correlation),
            (19, "时间趋势", self.test_temporal_trend),
            (20, "实体类型分布", self.test_entity_type_distribution),
            (21, "关系类型分布", self.test_relation_type_distribution),
            (22, "LLM降级", self.test_llm_fallback),
            (23, "阿文智能体", self.test_arabic_agent),
            (24, "图谱可视化数据", self.test_graph_visualization_data),
            (25, "报告生成", self.test_report_generation),
            (26, "多跳推理", self.test_multi_hop_reasoning),
            (27, "机构画像", self.test_institution_profiles),
            (28, "作者画像", self.test_author_profiles),
            (29, "推理期缩放", self.test_scaling_experiment),
            (30, "完整流程", self.test_full_pipeline),
        ]
        
        for test_id, name, func in tests:
            self.run_test(test_id, name, func)
        
        print()
        print("=" * 60)
        self._print_summary()
        
        return self.results
    
    def _print_summary(self):
        """打印测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        
        print(f"测试完成: {total}个")
        print(f"  ✅ 通过: {passed}")
        print(f"  ❌ 失败: {failed}")
        print(f"  ⚠️ 错误: {errors}")
        print(f"  通过率: {passed/total*100:.1f}%")
        
        total_time = sum(r["time"] for r in self.results)
        print(f"  总耗时: {total_time:.2f}s")
    
    def save_results(self, output_dir: Path = None):
        """保存测试结果"""
        if output_dir is None:
            output_dir = Path(__file__).parent / "test_results"
        
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. JSON 完整结果
        json_path = output_dir / f"test_results_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": timestamp,
                "total_tests": len(self.results),
                "results": self.results,
            }, f, ensure_ascii=False, indent=2)
        
        # 2. Markdown 报告
        md_path = output_dir / f"test_report_{timestamp}.md"
        self._save_markdown(md_path)
        
        # 3. 文本摘要
        txt_path = output_dir / f"test_summary_{timestamp}.txt"
        self._save_text_summary(txt_path)
        
        # 4. CSV 报表
        csv_path = output_dir / f"test_results_{timestamp}.csv"
        self._save_csv(csv_path)
        
        print(f"\n📁 结果已保存到: {output_dir}")
        print(f"  - JSON: {json_path.name}")
        print(f"  - Markdown: {md_path.name}")
        print(f"  - 文本: {txt_path.name}")
        print(f"  - CSV: {csv_path.name}")
        
        return {
            "json": json_path,
            "markdown": md_path,
            "text": txt_path,
            "csv": csv_path,
        }
    
    def _save_markdown(self, path: Path):
        """保存 Markdown 报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write("# SKWM 系统可行性测试报告\n\n")
            f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**测试总数**: {total}\n\n")
            f.write(f"**通过数**: {passed} ({passed/total*100:.1f}%)\n\n")
            f.write("---\n\n")
            
            f.write("## 测试结果详情\n\n")
            f.write("| 编号 | 测试名称 | 状态 | 耗时(s) | 备注 |\n")
            f.write("|------|----------|------|---------|------|\n")
            
            for r in self.results:
                status = "✅" if r["status"] == "PASS" else "❌" if r["status"] == "FAIL" else "⚠️"
                note = ""
                if "result" in r:
                    res = r["result"]
                    if "top_keyword" in res:
                        note = f"Top: {res['top_keyword']}"
                    elif "keyword" in res:
                        note = f"关键词: {res['keyword']}"
                    elif "correlation" in res:
                        note = f"相关系数: {res['correlation']}"
                    elif "hit_rate" in res:
                        note = f"命中率: {res['hit_rate']:.2%}"
                
                f.write(f"| {r['id']:02d} | {r['name']} | {status} | {r['time']:.3f} | {note} |\n")
            
            f.write("\n## 关键指标\n\n")
            
            # 数据规模
            data_test = next((r for r in self.results if r["id"] == 1), None)
            if data_test and "result" in data_test:
                res = data_test["result"]
                f.write(f"- **时间切片**: {res.get('snapshots', 0)}年\n")
                f.write(f"- **状态向量**: {res.get('state_vectors', 0):,}条\n")
            
            # Neo4j
            neo4j_test = next((r for r in self.results if r["id"] == 2), None)
            if neo4j_test and "result" in neo4j_test:
                res = neo4j_test["result"]
                f.write(f"- **Neo4j节点**: {res.get('nodes', 0):,}个\n")
                f.write(f"- **Neo4j边**: {res.get('edges', 0):,}条\n")
            
            # 闭环评测
            eval_test = next((r for r in self.results if r["id"] == 15), None)
            if eval_test and "result" in eval_test:
                res = eval_test["result"]
                f.write(f"- **闭环命中率**: {res.get('hit_rate', 0):.2%}\n")
            
            f.write("\n## 结论\n\n")
            if passed / total >= 0.8:
                f.write("✅ **系统可行性验证通过**，各模块功能正常，可进行生产部署。\n")
            else:
                f.write("⚠️ **系统存在问题**，需要修复后再进行部署。\n")
    
    def _save_text_summary(self, path: Path):
        """保存文本摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("SKWM 系统可行性测试摘要\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试总数: {total}\n")
            f.write(f"通过数: {passed}\n")
            f.write(f"失败数: {total - passed}\n")
            f.write(f"通过率: {passed/total*100:.1f}%\n\n")
            
            f.write("-" * 60 + "\n")
            f.write("测试详情:\n")
            f.write("-" * 60 + "\n\n")
            
            for r in self.results:
                status = "PASS" if r["status"] == "PASS" else "FAIL"
                f.write(f"[{status}] {r['id']:02d}. {r['name']} ({r['time']:.3f}s)\n")
                if "error" in r:
                    f.write(f"     错误: {r['error'][:100]}\n")
                f.write("\n")
            
            f.write("=" * 60 + "\n")
            if passed / total >= 0.8:
                f.write("结论: 系统可行性验证通过\n")
            else:
                f.write("结论: 系统存在问题，需要修复\n")
            f.write("=" * 60 + "\n")
    
    def _save_csv(self, path: Path):
        """保存 CSV 报表"""
        import csv
        
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["测试ID", "测试名称", "状态", "耗时(s)", "备注"])
            
            for r in self.results:
                note = ""
                if "result" in r:
                    res = r["result"]
                    note = str(res)[:100]
                elif "error" in r:
                    note = r["error"][:100]
                
                writer.writerow([
                    r["id"],
                    r["name"],
                    r["status"],
                    f"{r['time']:.3f}",
                    note,
                ])


if __name__ == "__main__":
    runner = TestRunner()
    results = runner.run_all()
    paths = runner.save_results()
    
    print("\n✅ 测试完成！")
