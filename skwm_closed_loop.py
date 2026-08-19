"""skwm_closed_loop.py — SKWM 世界模型外壳 (World-in-World -> 闭环规划)
====================================================================
从论文 World-in-World (arXiv:2510.18135) 迁移的闭环规划范式：
  propose->simulate->revise 策略引导束搜索。

依赖: numpy
可空跑验证逻辑; 接真实数据只需替换标了 # <-接现有 的地方。

用法:
    python skwm_closed_loop.py          # 空跑演示
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

# ============================================================
# 数据结构
# ============================================================

@dataclass
class KnowledgeState:
    """论文里的观测 o_t: 某年知识状态 S (=每个主题一个4维向量)"""
    year: int
    vec: dict[str, np.ndarray]          # topic -> [热度, 增速, 中心度, 连接数]

    def hot_topics(self, k: int = 10) -> list[str]:
        return sorted(self.vec, key=lambda t: self.vec[t][0], reverse=True)[:k]


@dataclass
class Plan:
    """论文里的候选动作序列 _: 一条研究/服务策略"""
    emphasis: dict[str, float] = field(default_factory=dict)     # 主题->权重 (+强调 / -弱化)
    edge_ops: list[tuple[str, str, str]] = field(default_factory=list)  # (op, u, v) op∈{add,remove}
    note: str = ""


# ============================================================
# ② 统一 Action API: I = C(_)
# ============================================================

class UnifiedStrategyAPI:
    """把抽象策略编码成对图谱/特征的干预"""
    
    def encode(self, plan: Plan) -> dict:
        return {
            "feature_shift": plan.emphasis,      # 施加到主题状态向量上的偏置
            "edge_interventions": plan.edge_ops,
        }

    def encode_batch(self, plans: list[Plan]) -> list[dict]:
        return [self.encode(p) for p in plans]


# ============================================================
# ③ 世界模型 g_θ: rollout 未来知识状态
# ============================================================

class KnowledgeWorldModel:
    """包装现有的 XGBoost 预测器, 提供 rollout 接口"""

    def __init__(self, data_layer=None, predictor=None):
        self.data = data_layer          # <-接现有 DataLayer(89年切片/状态向量)
        self.predictor = predictor      # <-接现有 XGBoost(AUC=未复现)

    def get_state(self, year: int) -> KnowledgeState:
        """获取某年知识状态"""
        if self.data is not None:
            return KnowledgeState(year, self.data.get_state(year))   # <-接现有
        # 空跑用随机数据
        topics = [f"topic_{i}" for i in range(20)]
        rng = np.random.default_rng(year)
        vec = {t: rng.random(4) * np.array([100, 0.5, 1.0, 50]) for t in topics}
        return KnowledgeState(year, vec)

    def rollout(self, o: KnowledgeState, control: dict, horizon: int) -> KnowledgeState:
        """论文公式(2): _ ~ g_θ(O | o, I)
        先施加干预, 再用趋势/链接预测外推 horizon 年。
        """
        vec = {t: v.copy() for t, v in o.vec.items()}

        # (a) 施加策略干预
        for topic, w in control.get("feature_shift", {}).items():
            if topic in vec:
                vec[topic][0] *= (1.0 + w)          # 调整初始热度
                vec[topic][1] += w * 0.1            # 增速微调

        # (b) 边干预 （桩: 真实逻辑在 data_layer.perturb_graph）
        # graph = self.data.perturb_graph(control["edge_interventions"])  # <-接现有

        # (c) 逐年外推
        for _ in range(horizon):
            for topic in vec:
                # 简化版演化: 热度 = 热度*(1+增速) + 随机噪声
                growth = vec[topic][1]
                noise = np.random.normal(0, 0.05)
                vec[topic][0] = max(0.0, vec[topic][0] * (1 + growth) + noise)
                # 增速微衰减 (热点趋于平稳)
                vec[topic][1] = vec[topic][1] * 0.95 + noise * 0.05
                # 连接数缓慢增长
                vec[topic][3] += max(0, noise * 2)

        return KnowledgeState(o.year + horizon, vec)


# ============================================================
# ① 提议策略 π_proposal
# ============================================================

class ProposalPolicy:
    """生成 M 条候选策略。有 LLM 用 LLM, 无则规则降级。"""

    def __init__(self, llm=None):
        self.llm = llm                    # <-接现有 DeepSeekClient

    def propose(self, o: KnowledgeState, goal: str, user: str, M: int) -> list[Plan]:
        if self.llm and getattr(self.llm, 'available', False):
            return self.llm.propose_plans(o.hot_topics(), goal, user, M)  # <-接现有

        # —— 规则降级: 从高增速主题生成 M 条差异化策略 ——
        by_growth = sorted(o.vec, key=lambda t: o.vec[t][1], reverse=True)
        plans = []
        for m in range(M):
            focus = by_growth[m:m+3]
            # 差异化: 交替强调/弱化
            weight = 0.5 if m % 2 == 0 else -0.3
            plans.append(Plan(
                emphasis={t: weight for t in focus},
                note=f"{'强调' if weight > 0 else '弱化'}新兴主题: {focus}"
            ))
        return plans


# ============================================================
# ③ 修订策略 π_revision (公式3/4): 打分并选最优
# ============================================================

class RevisionPolicy:
    """按服务对象打分，选期望收益最大的

    收窄后的服务关系：
      - 服务提供者：学科馆员
      - 主要服务对象：中阿文旅相关教师和科研团队
      - 主任务：新兴交叉主题识别
    """

    WEIGHTS = {
        "teacher":         dict(emergence=1.0, novelty=0.8, robustness=0.6, evidence=0.7),
        "research_team":   dict(emergence=0.9, novelty=0.9, robustness=0.7, evidence=0.8),
        "librarian":       dict(emergence=0.5, novelty=0.4, robustness=1.0, evidence=0.9),
    }

    def score(self, plan: Plan, fut: KnowledgeState, o: KnowledgeState, user: str) -> float:
        w = self.WEIGHTS.get(user, self.WEIGHTS["teacher"])

        # emergence: 推荐主题的热度增长
        emergence = sum(
            max(0, fut.vec[t][0] - o.vec[t][0])
            for t in plan.emphasis if t in fut.vec
        )
        # novelty: 推荐主题的平均增速
        novelty = float(np.mean([
            fut.vec[t][1] for t in plan.emphasis if t in fut.vec
        ] or [0]))
        # robustness: 推荐主题的中心度均值
        robustness = float(np.mean([
            fut.vec[t][2] for t in plan.emphasis if t in fut.vec
        ] or [0]))

        return (
            w["emergence"] * emergence +
            w["novelty"] * novelty +
            w["robustness"] * robustness
        )


# ============================================================
# 闭环控制器 (Algorithm 1 - 核心)
# ============================================================

class SKWMClosedLoopController:
    """propose->simulate->revise 闭环知识服务决策"""

    def __init__(self, kwm: KnowledgeWorldModel,
                 proposal: ProposalPolicy | None = None,
                 revision: RevisionPolicy | None = None,
                 api: UnifiedStrategyAPI | None = None):
        self.kwm = kwm
        self.proposal = proposal or ProposalPolicy()
        self.revision = revision or RevisionPolicy()
        self.api = api or UnifiedStrategyAPI()

    def decide(self, o: KnowledgeState, goal: str, user: str,
               M: int = 3, L: int = 5, B: int = 4) -> tuple[Plan, float]:
        """单步 propose->simulate->revise
        Args:
            M: 束宽 (提议数)
            L: 视野 (预测年数)
            B: 推理预算 (rollout 次数, 发现③)
        Returns:
            (最佳计划, 评分)
        """
        best_plan: Plan | None = None
        best_score = -1e9

        for plan in self.proposal.propose(o, goal, user, M):    # ① M 条候选
            I = self.api.encode(plan)                            # ② Action API
            # ③ 多次 rollout + 平均降方差
            futs = [self.kwm.rollout(o, I, L) for _ in range(B)]
            fut = self._avg(futs)
            s = self.revision.score(plan, fut, o, user)         # 打分
            if s > best_score:
                best_plan, best_score = plan, s

        assert best_plan is not None
        return best_plan, best_score

    def run(self, t0: int, T: int, goal: str, user: str,
            M: int = 3, L: int = 5, B: int = 4) -> list[dict]:
        """跨年运行闭环决策

        服务链：
          教师/科研团队提出需求
          → 馆员定义任务
          → Neo4j 检索事实和关系
          → 数据层形成年度知识状态
          → RSSM 预测未来状态
          → 服务层生成前沿报告
          → 馆员审核与反馈

        Args:
            t0: 起始年
            T: 结束年
            goal: 服务目标 (如 "识别中阿文旅前沿")
            user: 服务对象 (teacher / research_team / librarian)
        Returns:
            [{year, plan, score}, ...]
        """
        o = self.kwm.get_state(t0)
        decisions = []
        for t in range(t0, T + 1):
            plan, score = self.decide(o, goal, user, M, L, B)
            decisions.append({
                "year": t,
                "plan": plan,
                "score": round(float(score), 4)
            })
            o = self.kwm.get_state(t + 1) if t < T else o      # 观测新状态
        return decisions

    @staticmethod
    def _avg(states: list[KnowledgeState]) -> KnowledgeState:
        keys = states[0].vec.keys()
        vec = {t: np.mean([s.vec[t] for s in states], axis=0) for t in keys}
        return KnowledgeState(states[0].year, vec)


# ============================================================
# 闭环评测 (Closed-loop evaluation)
# ============================================================

class ClosedLoopEvaluator:
    """回测: 在 t 年做决策, 用 t+L 年真实数据检验 -> task success

    实现论文最强的方法论贡献: 用任务成功率而非表面指标评测。
    四类用户各有不同的闭环指标 (对应 SKWM.USER_TYPES)。
    """

    def __init__(self, kwm: KnowledgeWorldModel):
        self.kwm = kwm

    # ------ 指标1: 命中率 (学生 - 选题前瞻) ------
    def hit_rate(self, ctrl: SKWMClosedLoopController,
                 eval_years: list[int], user: str = "student",
                 L: int = 4, M: int = 5, B: int = 8, k: int = 10) -> float:
        """推荐主题在 L 年后跻身 Top-k 热点的命中率"""
        hits = 0
        n_total = 0
        for t in eval_years:
            o = self.kwm.get_state(t)
            plan, _ = ctrl.decide(o, goal="前沿识别", user=user,
                                  M=M, L=L, B=B)
            future_real = self.kwm.get_state(t + L)
            top_real = set(future_real.hot_topics(k))
            recommended = set(plan.emphasis)
            if recommended:
                hits += len(recommended & top_real)
                n_total += len(recommended)
        return hits / max(1, n_total)

    # ------ 指标2: Precision@k (教师 - 前沿识别) ------
    def precision_at_k(self, ctrl: SKWMClosedLoopController,
                       eval_years: list[int], user: str = "teacher",
                       L: int = 4, M: int = 5, B: int = 8, k: int = 5) -> float:
        """识别的爆发方向在 L 年后真正进入增速 Top-k 的比例"""
        hits = 0
        n_total = 0
        for t in eval_years:
            o = self.kwm.get_state(t)
            plan, _ = ctrl.decide(o, goal="前沿识别", user=user,
                                  M=M, L=L, B=B)
            future_real = self.kwm.get_state(t + L)
            emerging = sorted(future_real.vec,
                              key=lambda to: future_real.vec[to][1],
                              reverse=True)[:k]
            top_emerging = set(emerging)
            recommended = set(plan.emphasis)
            if recommended:
                hits += len(recommended & top_emerging)
                n_total += len(recommended)
        return hits / max(1, n_total)

    # ------ 指标3: 忠实度/可控性 (馆员 - 服务稳健性) ------
    def faithfulness(self, ctrl: SKWMClosedLoopController,
                     eval_years: list[int], user: str = "librarian",
                     L: int = 4, M: int = 5, B: int = 8) -> float:
        """反事实预测被真实数据印证的忠实度 (余弦相似度)"""
        sims = []
        for t in eval_years:
            o = self.kwm.get_state(t)
            plan, _ = ctrl.decide(o, goal="前沿识别", user=user,
                                  M=M, L=L, B=B)
            I = UnifiedStrategyAPI().encode(plan)
            predicted = self.kwm.rollout(o, I, L)
            real = self.kwm.get_state(t + L)
            common = [t for t in o.vec if t in predicted.vec and t in real.vec]
            for t in common:
                vp = predicted.vec[t]
                vr = real.vec[t]
                denom = (np.linalg.norm(vp) * np.linalg.norm(vr))
                if denom > 1e-10:
                    sims.append(np.dot(vp, vr) / denom)
        return float(np.mean(sims)) if sims else 0.0

    # ------ 指标4: Spearman rho (科研管理 - 趋势评估) ------
    def spearman_rho(self, ctrl: SKWMClosedLoopController,
                     eval_years: list[int], user: str = "manager",
                     L: int = 4, M: int = 5, B: int = 8) -> float:
        """预测排序 vs 真实排序的 Spearman 秩相关系数"""
        try:
            from scipy.stats import spearmanr
        except ImportError:
            print("  scipy not installed, using simplified ranking")
            return 0.0
        rhos = []
        for t in eval_years:
            o = self.kwm.get_state(t)
            plan, _ = ctrl.decide(o, goal="趋势评估", user=user,
                                  M=M, L=L, B=B)
            revision = RevisionPolicy()
            scores = {}
            for topic in o.vec:
                single_plan = Plan(emphasis={topic: 0.3})
                I = UnifiedStrategyAPI().encode(single_plan)
                fut = self.kwm.rollout(o, I, L)
                scores[topic] = revision.score(single_plan, fut, o, user)
            real = self.kwm.get_state(t + L)
            real_change = {t: real.vec[t][0] - o.vec[t][0] for t in o.vec}
            common = [t for t in scores if t in real_change]
            if len(common) < 3:
                continue
            rho, _ = spearmanr([scores[t] for t in common],
                               [real_change[t] for t in common])
            if not np.isnan(rho):
                rhos.append(rho)
        return float(np.mean(rhos)) if rhos else 0.0

    # ------ 综合报告 ------
    def full_report(self, ctrl: SKWMClosedLoopController,
                    eval_years: list[int],
                    L: int = 4, M: int = 5, B: int = 8, k: int = 10) -> dict:
        """四类用户的完整闭环评测报告"""
        return {
            "student_hit_rate": round(self.hit_rate(ctrl, eval_years, "student", L, M, B, k), 4),
            "teacher_precision@k": round(self.precision_at_k(ctrl, eval_years, "teacher", L, M, B, k), 4),
            "librarian_faithfulness": round(self.faithfulness(ctrl, eval_years, "librarian", L, M, B), 4),
            "manager_spearman_rho": round(self.spearman_rho(ctrl, eval_years, "manager", L, M, B), 4),
            "config": {"eval_years": eval_years, "L": L, "M": M, "B": B, "k": k},
        }


# ============================================================
# 主入口 (空跑验证)
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SKWM 闭环控制器 · 空跑演示")
    print("=" * 60)

    # 初始化组件
    kwm = KnowledgeWorldModel()
    proposal = ProposalPolicy()
    revision = RevisionPolicy()
    ctrl = SKWMClosedLoopController(kwm, proposal, revision)

    # 单步决策
    o = kwm.get_state(2020)
    print(f"\n[>] 起始状态: {o.year}, 主题数: {len(o.vec)}")
    print(f"   Top-5 热点: {o.hot_topics(5)}")

    plan, score = ctrl.decide(o, goal="前沿识别", user="student",
                              M=3, L=5, B=4)
    print(f"\n[>] 决策结果 (student):")
    print(f"   推荐策略: {plan.note}")
    print(f"   评分: {score:.4f}")
    print(f"   强调主题: {list(plan.emphasis.keys())[:5]}")

    # 跨年运行
    print(f"\n[>] 跨年运行 2020->2023 (manager):")
    decisions = ctrl.run(2020, 2023, goal="科研管理分析", user="manager",
                         M=4, L=3, B=6)
    for d in decisions:
        print(f"   {d['year']}: {d['plan'].note}  score={d['score']}")

    # 闭环评测
    evaluator = ClosedLoopEvaluator(kwm)
    hr = evaluator.hit_rate(ctrl, eval_years=[2018, 2019, 2020],
                            user="teacher", L=4, M=5, B=8, k=10)
    print(f"\n[>] 回测命中率 (teacher): {hr:.3f}")

    print("\n[OK]  外壳实现完成。接真实数据步骤:")
    print("  1. KnowledgeWorldModel.data = DataLayer()")
    print("  2. KnowledgeWorldModel.predictor = load_predictor()")
    print("  3. ProposalPolicy.llm = DeepSeekClient()")
    print("  4. 运行 ctrl.run() 或 evaluator.hit_rate()")
