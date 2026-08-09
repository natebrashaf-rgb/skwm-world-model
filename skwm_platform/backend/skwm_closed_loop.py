#!/usr/bin/env python3
"""
SKWM 闭环知识规划控制器
World-in-World 范式 → 中阿文旅知识世界模型

外壳: propose → simulate → revise 策略引导束搜索
对接: skwm_aligned_v4.py (DataLayer, 四类智能体, DeepSeekClient)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
import numpy as np
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════

@dataclass
class KnowledgeState:
    """
    论文里的观测 o_t
    中阿文旅: 某年知识状态 S (每个主题一个7维向量)
    [热度, 增速, 中心度, 连接数, 合作强度, 语言分布, 传播范围]
    """
    year: int
    vec: Dict[str, np.ndarray]  # topic -> 7维状态向量
    
    def hot_topics(self, k: int = 10) -> List[str]:
        """按热度排序返回Top-k主题"""
        return sorted(self.vec.keys(), 
                      key=lambda t: self.vec[t][0], reverse=True)[:k]
    
    def emerging_topics(self, k: int = 10) -> List[str]:
        """按增速排序返回Top-k新兴主题"""
        return sorted(self.vec.keys(),
                      key=lambda t: self.vec[t][1], reverse=True)[:k]
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "topics": {t: v.tolist() for t, v in self.vec.items()},
            "hot_topics": self.hot_topics(5),
            "emerging_topics": self.emerging_topics(5),
        }


@dataclass
class Plan:
    """
    论文里的候选动作序列 Â
    中阿文旅: 一条研究/服务策略
    """
    emphasis: Dict[str, float] = field(default_factory=dict)  # 主题->强调权重(+)/弱化(-)
    edge_ops: List[tuple] = field(default_factory=list)  # (op, u, v) op∈{add,remove}
    context_dim: str = "default"  # 语境维度 (national_policy/regional_coop/school_direction/global_situation)
    user_focus: str = "teacher"  # 用户类型侧重
    note: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "emphasis": self.emphasis,
            "edge_ops": self.edge_ops,
            "context_dim": self.context_dim,
            "user_focus": self.user_focus,
            "note": self.note,
        }


# ═══════════════════════════════════════════════════════════════════
# ② 统一 Action API: I = C(Â)
# ═══════════════════════════════════════════════════════════════════

class UnifiedStrategyAPI:
    """
    把抽象策略编码成对图谱/特征的干预
    复用 counterfactual() 的干预机制，扩展语境维度
    """
    
    CONTEXT_WEIGHTS = {
        "national_policy": {"一带一路": 1.5, "中阿合作": 1.3, "文化交流": 1.2},
        "regional_coop": {"中阿文旅中心": 1.4, "高校联盟": 1.2, "区域国别": 1.1},
        "school_direction": {"BISU": 1.3, "外语+旅游": 1.2, "学科交叉": 1.1},
        "global_situation": {"文明交流": 1.2, "可持续发展": 1.1, "数字文旅": 1.3},
        "default": {},
    }
    
    def encode(self, plan: Plan) -> Dict:
        """策略 → 图谱干预编码"""
        feature_shift = dict(plan.emphasis)
        
        # 叠加语境权重
        ctx_weights = self.CONTEXT_WEIGHTS.get(plan.context_dim, {})
        for topic, weight in ctx_weights.items():
            if topic in feature_shift:
                feature_shift[topic] *= weight
            else:
                feature_shift[topic] = weight - 1.0
        
        return {
            "feature_shift": feature_shift,
            "edge_interventions": plan.edge_ops,
            "context_dim": plan.context_dim,
        }


# ═══════════════════════════════════════════════════════════════════
# ③ 世界模型 g_θ: rollout 未来知识状态
# ═══════════════════════════════════════════════════════════════════

class KnowledgeWorldModel:
    """
    论文公式(2): Ô ~ g_θ(O | o, I)
    对接现有 DataLayer + XGBoost 预测器
    """
    
    def __init__(self, data_layer, predictor=None):
        self.data = data_layer
        self.predictor = predictor or getattr(data_layer, 'xgb_model', None)
    
    def get_state(self, year: int) -> KnowledgeState:
        """获取某年知识状态"""
        entities = self.data.get_entities(year)
        vec = {}
        for name, v in entities.items():
            if isinstance(v, (list, tuple)) and len(v) >= 4:
                # 扩展到7维
                arr = np.zeros(7)
                arr[:4] = v[:4]
                if len(v) >= 7:
                    arr[4:7] = v[4:7]
                else:
                    arr[4] = self.data._collab_intensity.get(name, 0)
                    arr[5] = 1.0 if self.data._detect_lang(name) in ["中文", "中阿混合"] else 0.0
                    arr[6] = len(self.data._entity_years.get(name, {year}))
                vec[name] = arr
        return KnowledgeState(year, vec)
    
    def rollout(self, o: KnowledgeState, control: Dict, horizon: int) -> KnowledgeState:
        """
        预测未来horizon年后的知识状态
        = 先施加干预(control), 再用趋势/链接预测外推
        """
        vec = {t: v.copy() for t, v in o.vec.items()}
        
        # (a) 施加策略干预 — 强调/弱化主题
        for topic, w in control.get("feature_shift", {}).items():
            if topic in vec:
                vec[topic][0] *= (1.0 + w)  # 调整初始热度
                vec[topic][1] *= (1.0 + w * 0.5)  # 增速也受影响
        
        # (b) 施加边干预 — 复用反事实逻辑
        # 这里简化处理，实际可调用 data.perturb_graph()
        
        # (c) 逐年外推 horizon 年
        for _ in range(horizon):
            for topic in list(vec.keys()):
                v = vec[topic]
                growth = v[1] * 0.01  # 增速归一化
                p_link = 0.1 * np.random.random()  # 简化: 随机链接概率
                
                # 热度演化
                v[0] = max(0.0, v[0] * (1 + growth) + p_link * 10)
                # 连接数演化
                v[3] += p_link
                # 合作强度演化
                v[4] += p_link * 0.5
        
        return KnowledgeState(o.year + horizon, vec)
    
    def counterfactual_rollout(self, o: KnowledgeState, remove_topic: str, horizon: int) -> KnowledgeState:
        """反事实rollout: 移除某主题后的未来预测"""
        vec = {t: v.copy() for t, v in o.vec.items() if t != remove_topic}
        
        # 移除相关边
        for topic in vec:
            vec[topic][3] *= 0.8  # 连接数下降
            vec[topic][4] *= 0.7  # 合作强度下降
        
        # 外推
        for _ in range(horizon):
            for topic in vec:
                v = vec[topic]
                v[0] *= 0.95  # 热度衰减
                v[1] *= 0.9   # 增速衰减
        
        return KnowledgeState(o.year + horizon, vec)


# ═══════════════════════════════════════════════════════════════════
# ① 提议策略 π_proposal
# ═══════════════════════════════════════════════════════════════════

class ProposalPolicy:
    """
    生成候选研究/服务策略
    对接 DeepSeekClient (无Key自动降级规则)
    """
    
    def __init__(self, llm=None):
        self.llm = llm
    
    def propose(self, o: KnowledgeState, goal: str, user: str, M: int,
                context_dim: str = "default") -> List[Plan]:
        """生成M条差异化策略"""
        if self.llm and getattr(self.llm, 'available', False):
            return self._llm_propose(o, goal, user, M, context_dim)
        return self._rule_propose(o, goal, user, M, context_dim)
    
    def _llm_propose(self, o: KnowledgeState, goal: str, user: str, 
                     M: int, context_dim: str) -> List[Plan]:
        """LLM生成策略"""
        hot = o.hot_topics(5)
        emerging = o.emerging_topics(5)
        
        prompt = f"""作为中阿文旅领域的学科服务规划器，请为{user}生成{M}条差异化的研究/服务策略。

当前热点: {hot}
新兴前沿: {emerging}
目标: {goal}
语境: {context_dim}

请返回JSON格式: [{{"emphasis": {{"主题1": 0.5, "主题2": 0.3}}, "note": "策略说明"}}]"""
        
        try:
            msgs = [
                {"role": "system", "content": "你是中阿文旅学科服务规划专家。返回纯JSON。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(msgs, temperature=0.7, max_tokens=500)
            import json
            plans_data = json.loads(response)
            return [
                Plan(emphasis=p.get("emphasis", {}), 
                     note=p.get("note", ""),
                     context_dim=context_dim,
                     user_focus=user)
                for p in plans_data[:M]
            ]
        except Exception as e:
            print(f"  [LLM提议失败: {e}]")
            return self._rule_propose(o, goal, user, M, context_dim)
    
    def _rule_propose(self, o: KnowledgeState, goal: str, user: str,
                      M: int, context_dim: str) -> List[Plan]:
        """规则降级: 生成M条差异化策略"""
        by_growth = o.emerging_topics(M * 3)
        by_heat = o.hot_topics(M * 2)
        
        plans = []
        
        # 策略1: 强调新兴主题
        if by_growth:
            focus = by_growth[:3]
            plans.append(Plan(
                emphasis={t: 0.5 for t in focus},
                context_dim=context_dim,
                user_focus=user,
                note=f"强调新兴主题: {focus}"
            ))
        
        # 策略2: 强调热点主题
        if by_heat:
            focus = by_heat[:3]
            plans.append(Plan(
                emphasis={t: 0.3 for t in focus},
                context_dim=context_dim,
                user_focus=user,
                note=f"巩固热点主题: {focus}"
            ))
        
        # 策略3: 混合策略
        if len(by_growth) >= 2 and len(by_heat) >= 2:
            mix = by_growth[:2] + by_heat[:2]
            plans.append(Plan(
                emphasis={t: 0.4 for t in mix},
                context_dim=context_dim,
                user_focus=user,
                note=f"新兴+热点混合: {mix}"
            ))
        
        # 策略4: 语境驱动
        ctx_topics = UnifiedStrategyAPI.CONTEXT_WEIGHTS.get(context_dim, {})
        if ctx_topics:
            plans.append(Plan(
                emphasis={t: 0.6 for t in list(ctx_topics.keys())[:3]},
                context_dim=context_dim,
                user_focus=user,
                note=f"语境驱动({context_dim}): {list(ctx_topics.keys())[:3]}"
            ))
        
        # 补充到M条
        while len(plans) < M:
            plans.append(Plan(
                emphasis={by_growth[len(plans) % len(by_growth)]: 0.3} if by_growth else {},
                context_dim=context_dim,
                user_focus=user,
                note=f"补充策略 #{len(plans)+1}"
            ))
        
        return plans[:M]


# ═══════════════════════════════════════════════════════════════════
# ③ 修订策略 π_revision (公式3/4)
# ═══════════════════════════════════════════════════════════════════

class RevisionPolicy:
    """
    按用户类型给 (计划, 模拟未来) 打分, 选期望收益最大的
    中阿文旅: 四类用户关注点不同
    """
    
    WEIGHTS = {
        "teacher":   dict(emergence=1.0, novelty=0.8, robustness=0.6, context_fit=0.7),
        "student":   dict(emergence=0.6, novelty=1.0, robustness=0.3, context_fit=0.5),
        "librarian": dict(emergence=0.5, novelty=0.4, robustness=1.0, context_fit=0.8),
        "manager":   dict(emergence=0.9, novelty=0.5, robustness=0.9, context_fit=0.9),
    }
    
    def score(self, plan: Plan, fut: KnowledgeState, o: KnowledgeState, 
              user: str, context_dim: str = "default") -> float:
        """计算策略得分"""
        w = self.WEIGHTS.get(user, self.WEIGHTS["teacher"])
        
        # 突现性: 强调主题的热度增长
        emergence = 0.0
        for t in plan.emphasis:
            if t in fut.vec and t in o.vec:
                delta = fut.vec[t][0] - o.vec[t][0]
                emergence += max(0, delta)
        
        # 新颖性: 强调主题的增速
        novelty_vals = [fut.vec[t][1] for t in plan.emphasis if t in fut.vec]
        novelty = np.mean(novelty_vals) if novelty_vals else 0
        
        # 稳健性: 强调主题的中心度
        robust_vals = [fut.vec[t][2] for t in plan.emphasis if t in fut.vec]
        robustness = np.mean(robust_vals) if robust_vals else 0
        
        # 语境契合度
        context_fit = 0.0
        ctx_topics = UnifiedStrategyAPI.CONTEXT_WEIGHTS.get(context_dim, {})
        for t in plan.emphasis:
            if t in ctx_topics:
                context_fit += ctx_topics[t] - 1.0
        
        score = (w["emergence"] * emergence + 
                 w["novelty"] * novelty + 
                 w["robustness"] * robustness +
                 w["context_fit"] * context_fit)
        
        return score


# ═══════════════════════════════════════════════════════════════════
# 闭环控制器 (Algorithm 1)
# ═══════════════════════════════════════════════════════════════════

class SKWMClosedLoopController:
    """
    SKWM 闭环知识规划控制器
    propose → simulate → revise 策略引导束搜索
    """
    
    def __init__(self, kwm: KnowledgeWorldModel, proposal: ProposalPolicy, 
                 revision: RevisionPolicy, api: Optional[UnifiedStrategyAPI] = None):
        self.kwm = kwm
        self.proposal = proposal
        self.revision = revision
        self.api = api or UnifiedStrategyAPI()
    
    def decide(self, o: KnowledgeState, goal: str, user: str, 
               M: int = 3, L: int = 5, B: int = 4,
               context_dim: str = "default") -> tuple[Plan, float]:
        """
        单步 propose→simulate→revise
        M=束宽(提议数), L=视野(预测年数), B=推理预算(rollout次数)
        """
        best, best_s = None, -1e9
        
        # ① 生成M条候选策略
        plans = self.proposal.propose(o, goal, user, M, context_dim)
        
        for plan in plans:
            # ② Action API: 策略 → 干预编码
            I = self.api.encode(plan)
            
            # ③ 多次rollout取平均 (推理期缩放, 发现③)
            futs = [self.kwm.rollout(o, I, L) for _ in range(B)]
            fut = self._avg(futs)
            
            # ④ 打分
            s = self.revision.score(plan, fut, o, user, context_dim)
            
            if s > best_s:
                best, best_s = plan, s
        
        return best, best_s
    
    def run(self, t0: int, T: int, goal: str, user: str,
            M: int = 3, L: int = 5, B: int = 4,
            context_dim: str = "default") -> List[Dict]:
        """
        跨年运行闭环规划
        返回每年的决策序列
        """
        o = self.kwm.get_state(t0)
        decisions = []
        
        for t in range(t0, T + 1):
            plan, s = self.decide(o, goal, user, M, L, B, context_dim)
            decisions.append({
                "year": t,
                "plan": plan.to_dict() if plan else {},
                "score": float(s),
            })
            # 观测新状态
            if t < T:
                o = self.kwm.get_state(t + 1)
        
        return decisions
    
    def counterfactual_analysis(self, year: int, remove_topic: str, 
                                horizon: int = 5) -> Dict:
        """反事实分析: 移除某主题后的影响"""
        o = self.kwm.get_state(year)
        
        # 正常rollout
        normal_future = self.kwm.rollout(o, {"feature_shift": {}}, horizon)
        
        # 反事实rollout
        cf_future = self.kwm.counterfactual_rollout(o, remove_topic, horizon)
        
        # 计算影响
        impact = 0.0
        affected_topics = []
        for t in o.vec:
            if t in normal_future.vec and t in cf_future.vec:
                delta = normal_future.vec[t][0] - cf_future.vec[t][0]
                if delta > 0:
                    impact += delta
                    affected_topics.append({"topic": t, "impact": float(delta)})
        
        affected_topics.sort(key=lambda x: -x["impact"])
        
        return {
            "year": year,
            "removed_topic": remove_topic,
            "horizon": horizon,
            "total_impact": float(impact),
            "affected_topics": affected_topics[:10],
            "conclusion": f"移除'{remove_topic}'后，整体知识热度下降{impact:.1f}",
        }
    
    @staticmethod
    def _avg(states: List[KnowledgeState]) -> KnowledgeState:
        """多个状态取平均"""
        if not states:
            return states[0]
        keys = states[0].vec.keys()
        vec = {t: np.mean([s.vec[t] for s in states if t in s.vec], axis=0) 
               for t in keys}
        return KnowledgeState(states[0].year, vec)


# ═══════════════════════════════════════════════════════════════════
# 闭环评测: Task Success
# ═══════════════════════════════════════════════════════════════════

class ClosedLoopEvaluator:
    """
    回测: 在t年用SKWM决策, 用t+L年真实数据检验 → 得到task success
    论文核心贡献: 用任务成功率而非表面指标评测
    """
    
    def __init__(self, kwm: KnowledgeWorldModel):
        self.kwm = kwm
    
    def hit_rate(self, ctrl: SKWMClosedLoopController, eval_years: List[int],
                 user: str, L: int = 4, M: int = 5, B: int = 8, 
                 k: int = 10, context_dim: str = "default") -> Dict:
        """
        命中率 = 推荐主题在L年后跻身Top-k热点的比例
        对应: 学生选题前瞻任务
        """
        hits = 0
        total = 0
        details = []
        
        for t in eval_years:
            o = self.kwm.get_state(t)
            plan, _ = ctrl.decide(o, "前沿识别", user, M, L, B, context_dim)
            
            # 真实未来
            future_real = self.kwm.get_state(t + L)
            top_real = set(future_real.hot_topics(k))
            
            # 推荐主题
            recommended = set(plan.emphasis.keys()) if plan else set()
            
            # 命中计算
            hit_count = len(recommended & top_real)
            hit_rate = hit_count / max(1, len(recommended))
            hits += hit_rate
            total += 1
            
            details.append({
                "year": t,
                "recommended": list(recommended)[:5],
                "actual_top": list(top_real)[:5],
                "hit_rate": hit_rate,
            })
        
        avg_hit_rate = hits / max(1, total)
        
        return {
            "metric": "hit_rate",
            "user": user,
            "eval_years": eval_years,
            "horizon": L,
            "avg_hit_rate": avg_hit_rate,
            "details": details,
            "interpretation": f"推荐主题在{L}年后跻身Top-{k}热点的命中率: {avg_hit_rate:.2%}",
        }
    
    def precision_at_k(self, ctrl: SKWMClosedLoopController, eval_years: List[int],
                       user: str, L: int = 4, k: int = 10) -> Dict:
        """
        Precision@k: 识别的"爆发方向"与真实爆发的精确率
        对应: 教师前沿识别任务
        """
        precisions = []
        
        for t in eval_years:
            o = self.kwm.get_state(t)
            # 识别的新兴主题 (按增速)
            identified = set(o.emerging_topics(k))
            
            # 真实未来爆发 (L年后热度增长最快的)
            future = self.kwm.get_state(t + L)
            growth = {topic: future.vec[topic][1] for topic in future.vec 
                      if topic in o.vec}
            actual_burst = set(sorted(growth.keys(), key=lambda x: -growth[x])[:k])
            
            prec = len(identified & actual_burst) / max(1, k)
            precisions.append(prec)
        
        avg_prec = np.mean(precisions) if precisions else 0
        
        return {
            "metric": "precision_at_k",
            "user": user,
            "k": k,
            "avg_precision": float(avg_prec),
            "interpretation": f"前沿识别精确率: {avg_prec:.2%}",
        }
    
    def faithfulness(self, ctrl: SKWMClosedLoopController, eval_years: List[int],
                     L: int = 4) -> Dict:
        """
        忠实度: 反事实预测被真实数据印证的比例
        对应: 馆员服务稳健性任务 (可控性>画质)
        """
        faithful_count = 0
        total = 0
        
        for t in eval_years:
            o = self.kwm.get_state(t)
            
            # 对Top-3热点做反事实
            for topic in o.hot_topics(3):
                # 预测: 移除后热度下降
                cf_future = self.kwm.counterfactual_rollout(o, topic, L)
                
                # 真实未来 (如果存在)
                try:
                    real_future = self.kwm.get_state(t + L)
                    if topic in real_future.vec:
                        # 检查预测方向是否正确
                        predicted_drop = o.vec[topic][0] - cf_future.vec.get(topic, np.zeros(7))[0]
                        actual_change = real_future.vec[topic][0] - o.vec[topic][0]
                        
                        # 如果预测下降，实际也确实下降或平稳，算忠实
                        if predicted_drop > 0 and actual_change <= predicted_drop * 0.5:
                            faithful_count += 1
                        total += 1
                except:
                    pass
        
        faithfulness = faithful_count / max(1, total)
        
        return {
            "metric": "faithfulness",
            "eval_years": eval_years,
            "faithfulness": faithfulness,
            "interpretation": f"反事实预测忠实度: {faithfulness:.2%}",
        }


# ═══════════════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════════════

def create_controller(data_layer, llm_client=None) -> SKWMClosedLoopController:
    """创建闭环控制器"""
    kwm = KnowledgeWorldModel(data_layer)
    proposal = ProposalPolicy(llm_client)
    revision = RevisionPolicy()
    api = UnifiedStrategyAPI()
    return SKWMClosedLoopController(kwm, proposal, revision, api)


def create_evaluator(data_layer) -> ClosedLoopEvaluator:
    """创建闭环评测器"""
    kwm = KnowledgeWorldModel(data_layer)
    return ClosedLoopEvaluator(kwm)


# ═══════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from skwm_aligned_v4 import DataLayer, DeepSeekClient
    
    print("🧪 测试 SKWM 闭环控制器...")
    
    # 加载数据
    data = DataLayer().load(verbose=True)
    ds = DeepSeekClient()
    
    # 创建控制器
    ctrl = create_controller(data, ds)
    
    # 测试单步决策
    print("\n📋 单步决策测试:")
    o = ctrl.kwm.get_state(2020)
    plan, score = ctrl.decide(o, "识别中阿文旅前沿", "student", M=3, L=3, B=2)
    print(f"  策略: {plan.note if plan else 'None'}")
    print(f"  得分: {score:.3f}")
    
    # 测试跨年运行
    print("\n📅 跨年规划测试 (2020-2023):")
    decisions = ctrl.run(2020, 2023, "中阿文旅研究", "teacher", M=2, L=2, B=2)
    for d in decisions:
        print(f"  {d['year']}: {d['plan'].get('note', '')[:40]}... (score={d['score']:.3f})")
    
    # 测试反事实分析
    print("\n🔍 反事实分析测试:")
    cf = ctrl.counterfactual_analysis(2020, "一带一路", horizon=3)
    print(f"  移除'一带一路'影响: {cf['total_impact']:.2f}")
    print(f"  受影响主题: {[t['topic'] for t in cf['affected_topics'][:3]]}")
    
    print("\n✅ 测试完成")
