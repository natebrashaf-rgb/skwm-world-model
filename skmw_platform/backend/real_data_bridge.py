"""real_data_bridge.py — 桥接：用 B1 JSON + state_vectors 提供 KnowledgeWorldModel 接口"""
import json, re
from pathlib import Path
from collections import defaultdict
from skwm_closed_loop import KnowledgeState, KnowledgeWorldModel

class BridgeKnowledgeWorldModel(KnowledgeWorldModel):
    """用 rail_deploy/data/ 下的 JSON 文件提供真实数据"""

    def __init__(self, papers: list, state_vectors: dict, rssm_adapter=None):
        super().__init__()
        self.papers = papers
        self.state_vectors = state_vectors
        self.rssm_adapter = rssm_adapter  # 真正的 RSSM 预测器
        years = sorted([int(k) for k in state_vectors.keys() if k != '_wm'])
        self.year_range = (years[0], years[-1]) if years else (1895, 2026)
        latest_year = str(years[-1]) if years else '2026'
        self.topics = list(state_vectors.get(latest_year, {}).keys())[:100]
        self.topic_names = {t: t for t in self.topics}
        by_year = defaultdict(list)
        by_cat = defaultdict(list)
        for p in papers:
            y = p.get('year', 0)
            try: by_year[int(y)].append(p)
            except: pass
            for kw in (p.get('keywords') or []):
                if kw: by_cat[kw.strip()].append(p)
        self.data = {'total': len(papers), 'by_year': dict(by_year),
                     'by_category': dict(by_cat), 'all': papers}

    def get_state(self, year: int) -> KnowledgeState:
        s = str(year)
        yd = self.state_vectors.get(s, {})
        vec = {}
        for t in self.topics:
            v = yd.get(t, [0, 0, 0.0, 0])
            vec[t] = [float(x) for x in v]
        return KnowledgeState(vec=vec, year=year)

    def rollout(self, o: KnowledgeState, control: dict, horizon: int) -> KnowledgeState:
        """如果 RSSM 可用就用 RSSM 预测，否则用简单线性外推"""
        if self.rssm_adapter is not None:
            try:
                return self.rssm_adapter.rollout(o, control, horizon)
            except Exception as e:
                print(f"  ⚠️ RSSM 预测失败，回退到线性外推: {e}")
        # 兜底：简单线性外推
        import numpy as np
        vec = {}
        for t in o.vec:
            old = o.vec[t]
            growth = control.get('growth_rate', 0.02)
            vec[t] = [old[0] * (1 + growth), old[1] * (1 + growth), old[2], old[3]]
        return KnowledgeState(vec=vec, year=o.year + horizon)
