"""real_data_layer.py — 从文献资料库读取真实数据，构建知识状态向量
====================================================================
替代 skwm_closed_loop.py 中的 KnowledgeWorldModel 随机数据桩。

数据源: D:\vault\sheer\世界模型\📚_文献资料库\📚_文献资料库\
  每个分类下有 📖_文献目录.md (Markdown表格: 标题/作者/年份/期刊/引用)
  还有 _阿语文献.json / 阿语_*.md 等阿语特色资源

用法:
    from real_data_layer import RealKnowledgeWorldModel
    kwm = RealKnowledgeWorldModel()
    state = kwm.get_state(2020)   # 返回真实知识状态
"""
from __future__ import annotations
import os, re, json
from pathlib import Path
from collections import defaultdict
import numpy as np
from skwm_closed_loop import KnowledgeState, Plan

# ============================================================
# 配置：文献资料库路径
# ============================================================

LIT_BASE = Path(os.environ.get(
    "SKWM_LIT_BASE",
    "D:/vault/sheer/世界模型/📚_文献资料库/📚_文献资料库"
))

# 核心分类（用于构建知识状态）
CORE_CATEGORIES = [
    "01_科学知识世界模型_SKWM",
    "02_知识图谱_KnowledgeGraph",
    "03_GraphRAG_RAG",
    "04_大模型智能体_LLMAgent",
    "05_科学计量与科学地图",
    "06_高校图书馆学科服务",
    "07_中阿文旅与文化遗产",
    "08_数字文旅与旅游传播",
    "09_多语种知识组织",
    "10_AI赋能图书馆",
]

EXT_CATEGORIES = [
    "21_文化遗产旅游延伸",
    "22_数字文旅延伸",
    "23_中阿文明交流",
    "24_阿拉伯旅游传播",
    "25_跨界交叉选题",
]

# ============================================================
# 解析文献目录 Markdown 表格
# ============================================================

def parse_table_row(line: str) -> dict | None:
    """解析 | # | 标题 | 作者 | 年份 | 期刊 | 引用 | 格式的一行"""
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return None
    cells = [c.strip() for c in line.split("|")[1:-1]]
    if len(cells) < 6:
        return None
    title = cells[1]  # 第2列是标题
    # 跳过表头和空行
    if title in ("", "标题", "Title"):
        return None
    year_str = cells[3]  # 第4列是年份
    cites_str = cells[5]  # 第6列是引用数
    try:
        year = int(year_str)
    except ValueError:
        year = 0
    try:
        cites = int(cites_str.replace(",", ""))
    except ValueError:
        cites = 0
    return {
        "title": title,
        "year": year,
        "citations": cites,
        "journal": cells[4] if len(cells) > 4 else "",  # 第5列是期刊
        "authors": cells[2] if len(cells) > 2 else "",  # 第3列是作者
    }

def load_category(cat_name: str) -> list[dict]:
    """加载一个分类下的所有文献"""
    md_path = LIT_BASE / cat_name / "📖_文献目录.md"
    if not md_path.exists():
        print(f"  ⚠ 未找到: {md_path}")
        return []
    papers = []
    with open(md_path, "r", encoding="utf-8") as f:
        in_table = False
        for line in f:
            if "|---" in line:
                in_table = True
                continue
            if in_table:
                row = parse_table_row(line)
                if row and row["year"] > 0:
                    row["category"] = cat_name
                    papers.append(row)
    return papers

# ============================================================
# 加载全部文献数据
# ============================================================

def load_all() -> dict:
    """加载全部文献，返回按分类和年份组织的字典"""
    all_papers = []
    for cat in CORE_CATEGORIES:
        papers = load_category(cat)
        all_papers.extend(papers)
        print(f"  {cat}: {len(papers)} 篇")

    # 按分类统计
    by_cat = defaultdict(list)
    for p in all_papers:
        by_cat[p["category"]].append(p)

    # 按年份统计
    by_year = defaultdict(list)
    for p in all_papers:
        by_year[p["year"]].append(p)

    return {
        "total": len(all_papers),
        "by_category": dict(by_cat),
        "by_year": dict(by_year),
        "all": all_papers,
    }

# ============================================================
# 真实知识世界模型
# ============================================================

class RealKnowledgeWorldModel:
    """基于真实文献数据的 KnowledgeWorldModel"""

    def __init__(self):
        print("📚 加载真实文献数据...")
        self.data = load_all()
        print(f"  共 {self.data['total']} 篇真实文献")

        # 构建主题列表（每个分类 = 一个主题）
        self.topics = CORE_CATEGORIES.copy()
        # 为每个分类构建简明名称
        self.topic_names = {
            c: c.split("_", 1)[1].replace("_", " ") if "_" in c else c
            for c in self.topics
        }
        # 年份范围
        years = [y for y in self.data["by_year"].keys() if 2000 <= y <= 2026]
        self.year_range = (min(years), max(years)) if years else (2018, 2026)

    def get_state(self, year: int) -> KnowledgeState:
        """构建某年的真实知识状态
        每个主题(topic) = 该分类 + 该年的文献统计
        状态向量: [论文数, 年增长率, 引用中心度, 累计连接数]
        """
        vec = {}
        for topic in self.topics:
            papers = self.data["by_category"].get(topic, [])
            # 该年论文数
            year_papers = [p for p in papers if p["year"] == year]
            n_year = len(year_papers)
            # 上年论文数（用于计算增长率）
            prev_papers = [p for p in papers if p["year"] == year - 1]
            n_prev = len(prev_papers)
            growth = (n_year - n_prev) / max(1, n_prev) if n_prev > 0 else 0.0
            # 总引用数（中心度指标）
            total_cites = sum(p["citations"] for p in papers if p["year"] <= year)
            # 累计连接数（累计论文数）
            cumulative = len([p for p in papers if p["year"] <= year])
            vec[topic] = np.array([
                float(n_year),           # 热度 = 当年论文数
                float(growth),           # 增速
                float(np.log1p(total_cites)),  # 中心度 = log(总引用+1)
                float(cumulative),       # 连接数
            ])
        return KnowledgeState(year, vec)

    def hot_topics(self, year: int, k: int = 5) -> list[tuple[str, float]]:
        """返回某年最热门的 k 个主题"""
        state = self.get_state(year)
        scored = [(t, state.vec[t][0]) for t in self.topics]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.topic_names.get(t, t), s) for t, s in scored[:k]]

    def emerging_topics(self, year: int, k: int = 5) -> list[tuple[str, float]]:
        """返回某年增速最快的 k 个主题"""
        state = self.get_state(year)
        scored = [(t, state.vec[t][1]) for t in self.topics]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.topic_names.get(t, t), s) for t, s in scored[:k]]

    def summary(self, year: int) -> dict:
        """返回某年的完整概要"""
        state = self.get_state(year)
        return {
            "year": year,
            "total_papers": self.data["total"],
            "topics": {self.topic_names.get(t, t): state.vec[t].tolist()
                      for t in self.topics},
            "hot_topics": self.hot_topics(year, 5),
            "emerging_topics": self.emerging_topics(year, 5),
        }

    # ============ 对接闭环控制器 ============

    def rollout(self, o: KnowledgeState, control: dict, horizon: int) -> KnowledgeState:
        """闭环控制器需要的 rollout 接口
        基于真实数据趋势外推: 用历史增长率预测未来
        """
        vec = {}
        for topic in self.topics:
            v = o.vec.get(topic, np.zeros(4)).copy()
            # 获取历史平均增速
            papers = self.data["by_category"].get(topic, [])
            recent_years = [p["year"] for p in papers
                          if p["year"] <= o.year and p["year"] >= o.year - 3]
            n_hist = len(recent_years)
            avg_growth = v[1] if n_hist < 2 else v[1]

            # 施加策略干预
            shift = control.get("feature_shift", {}).get(topic, 0)
            if shift:
                v[0] *= (1.0 + shift)      # 调整热度
                v[1] += shift * 0.1         # 调整增速

            # 外推 horizon 年
            for _ in range(horizon):
                growth = v[1] + np.random.normal(0, 0.02)  # 加小噪声
                v[0] = max(0.0, v[0] * (1 + growth))
                v[1] = v[1] * 0.95 + growth * 0.05
                v[3] += max(0, np.random.normal(0.5, 0.3))

            vec[topic] = v

        return KnowledgeState(o.year + horizon, vec)


# ============================================================
# 主入口：验证真实数据
# ============================================================

if __name__ == "__main__":
    kwm = RealKnowledgeWorldModel()

    print(f"\n年份范围: {kwm.year_range}")
    print()

    for year in [2020, 2022, 2024]:
        print(f"=== {year} 年 ===")
        state = kwm.get_state(year)
        print(f"  主题数: {len(state.vec)}")
        hot = kwm.hot_topics(year)
        print(f"  热门主题: {hot}")
        em = kwm.emerging_topics(year)
        print(f"  增长最快: {em}")
        # 打印各主题的论文数
        for t in kwm.topics:
            v = state.vec[t]
            if v[0] > 0:  # 只显示有论文的
                name = kwm.topic_names[t]
                print(f"    {name}: {int(v[0])}篇, 增速{v[1]:+.1%}, 引用指数{v[2]:.1f}")
        print()

    # 测试闭环规划用真实数据
    print("=== 用真实数据跑闭环规划 ===")
    from skwm_closed_loop import SKWMClosedLoopController, ProposalPolicy, RevisionPolicy

    ctrl = SKWMClosedLoopController(kwm, ProposalPolicy(), RevisionPolicy())
    decisions = ctrl.run(t0=2020, T=2023, goal="前沿识别", user="teacher", M=4, L=3, B=6)
    for d in decisions:
        print(f"  {d['year']}: score={d['score']:.1f}  {d['plan'].note}")
