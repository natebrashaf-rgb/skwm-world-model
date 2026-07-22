#!/usr/bin/env python3
"""
skwm_context.py —— C 语境变量引擎（把 C 从 🟡框架 升级到 ✅参与计算）

对应策划案第60条：C = 语境变量（国家政策 / 区域合作 / 学校学科方向 / 国际形势）

核心思想：语境不再是一个字符串标签，而是一组"主题加权规则"。
给定 (当前年份, 用户类型)，ContextEngine 会对每个知识主题算出一个
语境权重 w(topic)，用它去重排 S(热点)、T(前沿/预测) 的结果。
这样"教师 vs 管理"、"2013 前 vs 后"就会得到不同的排序 —— C 真正介入了计算。

完全离线：只读同目录下的 context.json，不依赖任何实时 API。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).parent


class ContextEngine:
    def __init__(self, context_path: Optional[Path] = None):
        self.path = Path(context_path) if context_path else (BASE_DIR / "context.json")
        self.ctx = {}
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self.ctx = json.load(f)
        return self

    # ── 核心：给某个主题算语境权重 ───────────────────────────────
    def topic_weight(self, topic: str, year: int, user_type: str = "teacher") -> float:
        """返回 topic 在 (year, user_type) 语境下的加权系数（默认 1.0 = 不加权）"""
        name = (topic or "").lower()
        weight = 1.0
        bias = self.ctx.get("user_context_bias", {}).get(user_type, {})

        def _match(boost_topics):
            return any(bt.lower() in name or name in bt.lower() for bt in boost_topics)

        # 国家政策：只有到达/超过政策年份才生效（体现时间性 T×C）
        for pol in self.ctx.get("national_policy", []):
            if year >= pol.get("year", 0) and _match(pol.get("boost_topics", [])):
                weight *= pol.get("weight", 1.0) * bias.get("national_policy", 1.0)

        # 区域合作
        for rc in self.ctx.get("regional_coop", []):
            if _match(rc.get("boost_topics", [])):
                weight *= rc.get("weight", 1.0) * bias.get("regional_coop", 1.0)

        # 学校学科方向
        sd = self.ctx.get("school_direction", {})
        if _match(sd.get("boost_topics", [])):
            weight *= sd.get("weight", 1.0) * bias.get("school_direction", 1.0)

        # 国际形势
        for gs in self.ctx.get("global_situation", []):
            if _match(gs.get("boost_topics", [])):
                weight *= gs.get("weight", 1.0) * bias.get("global_situation", 1.0)

        return round(weight, 4)

    # ── 对一批主题重排（热点/前沿通用）───────────────────────────
    def reweight(self, items: List[Dict], year: int, user_type: str = "teacher",
                 score_key: str = "heat") -> List[Dict]:
        """对含有 name + score_key 的列表按语境加权后重排，返回新列表。"""
        out = []
        for it in items:
            w = self.topic_weight(it.get("name", ""), year, user_type)
            base = it.get(score_key, 0) or 0
            new_it = dict(it)
            new_it["context_weight"] = w
            new_it["context_score"] = round(base * w, 4)
            out.append(new_it)
        out.sort(key=lambda x: -x["context_score"])
        return out

    def active_dims(self, year: int) -> List[str]:
        """返回当前年份下已激活的语境维度（用于前端展示 C 的取值）"""
        dims = []
        if any(year >= p.get("year", 0) for p in self.ctx.get("national_policy", [])):
            dims.append("national_policy")
        if self.ctx.get("regional_coop"):
            dims.append("regional_coop")
        if self.ctx.get("school_direction"):
            dims.append("school_direction")
        if self.ctx.get("global_situation"):
            dims.append("global_situation")
        return dims


if __name__ == "__main__":
    ce = ContextEngine()
    demo = [
        {"name": "数字文旅与文化遗产保护", "heat": 0.80},
        {"name": "generative ai", "heat": 0.60},
        {"name": "阿拉伯语教学", "heat": 0.50},
        {"name": "其他冷门主题", "heat": 0.85},
    ]
    print("== teacher @2026 ==")
    for x in ce.reweight(demo, 2026, "teacher"):
        print(f"  {x['name']:20s} heat={x['heat']} w={x['context_weight']} -> {x['context_score']}")
