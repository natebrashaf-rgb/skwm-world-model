#!/usr/bin/env python3
"""
中阿文旅科学知识世界模型
============================
基于 World-in-World 闭循环规划算法
应用于「科学知识世界模型驱动的高校图书馆智能学科服务模式」

将原论文的"网格世界"替换为"中阿文旅知识世界"：
- 智能体 → 学科馆员 / 大模型智能体
- 环境 → 中阿文旅学术知识世界
- 动作 → 检索 / 分析 / 推荐 / 问答
- 世界模型 → 知识图谱 + GraphRAG 预测
"""

import numpy as np
import random
from typing import List, Tuple, Dict, Optional, Any
from collections import defaultdict
import json


# ============================================================================
# 第一部分：模拟中阿文旅知识库（还没建真实的，先用模拟数据）
# ============================================================================

class SinoArabKnowledgeBase:
    """
    模拟中阿文旅知识库。
    
    在完整实现中，这对应：
    - 中阿英文旅术语库
    - 中阿文旅知识图谱
    - 引文网络和合作网络
    - 科学计量数据库
    
    这里用字典构建模拟数据，涵盖论文中的七类知识实体。
    """
    
    def __init__(self):
        # ====== 文献数据 ======
        self.papers = {
            "P001": {"title": "中阿文化遗产数字化保护路径研究", 
                     "year": 2024, "authors": ["张明", "Ahmed Hassan"], 
                     "keywords": ["文化遗产", "数字化", "中阿合作"],
                     "lang": "中文", "citations": 12},
            "P002": {"title": "丝绸之路旅游廊道建设与跨文化传播",
                     "year": 2024, "authors": ["李华", "王芳", "Sara Al-Ali"],
                     "keywords": ["丝绸之路", "旅游廊道", "跨文化传播"],
                     "lang": "中文", "citations": 8},
            "P003": {"title": "التراث الثقافي والسياحة في الدول العربية",
                     "year": 2023, "authors": ["Mohammed Ali", "刘洋"],
                     "keywords": ["تراث ثقافي", "سياحة", "التعاون الصيني العربي"],
                     "lang": "阿拉伯语", "citations": 5},
            "P004": {"title": "Digital Transformation of Cultural Heritage Tourism in the Belt and Road Initiative",
                     "year": 2024, "authors": ["Chen Wei", "Fatima Al-Zahra"],
                     "keywords": ["digital heritage", "Belt and Road", "cultural tourism"],
                     "lang": "英文", "citations": 15},
            "P005": {"title": "中阿旅游合作对区域经济的影响研究",
                     "year": 2023, "authors": ["赵强", "李华"],
                     "keywords": ["旅游合作", "区域经济", "中阿关系"],
                     "lang": "中文", "citations": 6},
            "P006": {"title": "中国游客赴阿联酋旅游行为分析",
                     "year": 2024, "authors": ["王芳", "Sarah Johnson"],
                     "keywords": ["中国游客", "阿联酋", "旅游行为"],
                     "lang": "中文", "citations": 9},
            "P007": {"title": "دور التكنولوجيا الحديثة في تطوير السياحة الثقافية",
                     "year": 2024, "authors": ["Khalid Al-Rashid"],
                     "keywords": ["التكنولوجيا", "السياحة الثقافية", "الابتكار"],
                     "lang": "阿拉伯语", "citations": 3},
            "P008": {"title": "AI-Powered Knowledge Services for Cross-Cultural Tourism Research",
                     "year": 2025, "authors": ["Zhang Ming", "Chen Wei", "Li Hua"],
                     "keywords": ["AI", "knowledge service", "cross-cultural tourism"],
                     "lang": "英文", "citations": 4},
            "P009": {"title": "沙特阿拉伯\u201c2030愿景\u201d中的文旅融合战略",
                     "year": 2024, "authors": ["周瑜", "赵强"],
                     "keywords": ["沙特", "2030愿景", "文旅融合"],
                     "lang": "中文", "citations": 7},
            "P010": {"title": "中阿高校旅游管理学科合作网络分析",
                     "year": 2023, "authors": ["刘洋", "Ahmed Hassan", "李华"],
                     "keywords": ["旅游教育", "学科合作", "中阿高校"],
                     "lang": "中文", "citations": 4},
            "P011": {"title": "السياحة المستدامة في المنطقة العربية",
                     "year": 2024, "authors": ["Nadia Mansour", "周瑜"],
                     "keywords": ["سياحة مستدامة", "البيئة", "التنمية"],
                     "lang": "阿拉伯语", "citations": 6},
            "P012": {"title": "基于大语言模型的阿拉伯语文献智能检索系统",
                     "year": 2025, "authors": ["张明", "王芳"],
                     "keywords": ["大语言模型", "阿拉伯语", "智能检索"],
                     "lang": "中文", "citations": 3},
        }
        
        # ====== 主题分类 ======
        self.topics = {
            "文化遗产数字化": {"papers": ["P001", "P004"], "热度": 0.85},
            "旅游合作与经济": {"papers": ["P005", "P009"], "热度": 0.75},
            "跨文化旅游传播": {"papers": ["P002", "P006"], "热度": 0.70},
            "阿拉伯文旅政策": {"papers": ["P007", "P009", "P011"], "热度": 0.65},
            "AI与知识服务": {"papers": ["P008", "P012"], "热度": 0.80},
            "旅游教育与科研": {"papers": ["P010"], "热度": 0.50},
            "可持续旅游": {"papers": ["P011"], "热度": 0.60},
        }
        
        # ====== 机构数据 ======
        self.institutions = {
            "北京第二外国语学院": {"papers": ["P002", "P005", "P010", "P012"], "country": "中国"},
            "开罗大学": {"papers": ["P001", "P010"], "country": "埃及"},
            "阿联酋大学": {"papers": ["P006"], "country": "阿联酋"},
            "沙特国王大学": {"papers": ["P009"], "country": "沙特"},
            "北京外国语大学": {"papers": ["P003", "P011"], "country": "中国"},
            "中山大学": {"papers": ["P004", "P008"], "country": "中国"},
        }
        
        # ====== 政策文件 ======
        self.policies = {
            "POL001": {"name": "中阿合作论坛2024-2026行动计划", "year": 2024, 
                       "type": "国际合作", "related_topics": ["旅游合作与经济", "文化遗产数字化"]},
            "POL002": {"name": "沙特2030愿景旅游战略", "year": 2023,
                       "type": "国家战略", "related_topics": ["阿拉伯文旅政策", "可持续旅游"]},
            "POL003": {"name": "中国\u201c一带一路\u201d文旅合作指导意见", "year": 2024,
                       "type": "国家政策", "related_topics": ["旅游合作与经济", "跨文化旅游传播"]},
            "POL004": {"name": "埃及文化旅游振兴计划", "year": 2024,
                       "type": "国家计划", "related_topics": ["文化遗产数字化", "可持续旅游"]},
        }
        
        # ====== 科研项目 ======
        self.projects = {
            "PRJ001": {"name": "中阿文化遗产数字化保护与智能服务", "fund": "国家社科基金", "year": 2024},
            "PRJ002": {"name": "一带一路文旅融合与国际传播研究", "fund": "教育部人文社科", "year": 2023},
            "PRJ003": {"name": "阿拉伯语资源智能处理与知识服务平台", "fund": "北京市社科基金", "year": 2024},
        }
        
        # 构建引文网络
        self.citation_network = {
            "P001": ["P004", "P008"],
            "P002": ["P005", "P010"],
            "P003": ["P001", "P011"],
            "P004": ["P008"],
            "P005": ["P009"],
            "P006": [],
            "P007": ["P003", "P011"],
            "P008": [],
            "P009": ["P004"],
            "P010": ["P008"],
            "P011": ["P007"],
            "P012": ["P008"],
        }
        
        # 合作网络
        self.coauthor_network = self._build_coauthor_network()
        
        # 术语对齐表（中⇄阿⇄英）
        self.term_alignment = {
            "文化遗产": {"ar": "تراث ثقافي", "en": "cultural heritage"},
            "文化旅游": {"ar": "سياحة ثقافية", "en": "cultural tourism"},
            "数字化": {"ar": "رقمنة", "en": "digitalization"},
            "可持续发展": {"ar": "تنمية مستدامة", "en": "sustainable development"},
            "一带一路": {"ar": "الحزام والطريق", "en": "Belt and Road"},
            "中阿合作": {"ar": "التعاون الصيني العربي", "en": "China-Arab cooperation"},
        }
    
    def _build_coauthor_network(self):
        """构建作者合作网络"""
        network = defaultdict(set)
        for pid, paper in self.papers.items():
            authors = paper["authors"]
            for i, a1 in enumerate(authors):
                for a2 in authors[i+1:]:
                    network[a1].add(a2)
                    network[a2].add(a1)
        return {k: list(v) for k, v in network.items()}
    
    def search(self, query: str, lang: str = "中文", max_results: int = 5) -> List[Dict]:
        """模拟文献检索"""
        results = []
        query_lower = query.lower()
        for pid, paper in self.papers.items():
            score = 0
            # 标题匹配
            if query_lower in paper["title"].lower():
                score += 3
            # 关键词匹配
            for kw in paper["keywords"]:
                if query_lower in kw.lower():
                    score += 2
            # 语言过滤
            if lang != "全部" and paper["lang"] != lang:
                continue
            if score > 0:
                results.append({"pid": pid, "paper": paper, "score": score})
        
        results.sort(key=lambda x: (-x["score"], -x["paper"]["citations"]))
        return results[:max_results]
    
    def get_topic_hotspots(self) -> List[Dict]:
        """获取主题热度排名（科学计量功能）"""
        sorted_topics = sorted(
            self.topics.items(),
            key=lambda x: (-x[1]["热度"], -len(x[1]["papers"]))
        )
        result = []
        for topic, info in sorted_topics:
            papers_info = [self.papers[pid]["title"] for pid in info["papers"]]
            result.append({
                "topic": topic,
                "heat": info["热度"],
                "paper_count": len(info["papers"]),
                "representative_papers": papers_info[:3],
            })
        return result
    
    def get_institution_ranking(self) -> List[Dict]:
        """机构排名"""
        ranking = []
        for inst, info in sorted(self.institutions.items(),
                                  key=lambda x: -len(x[1]["papers"])):
            ranking.append({
                "name": inst,
                "country": info["country"],
                "paper_count": len(info["papers"]),
                "papers": [self.papers[pid]["title"] for pid in info["papers"]],
            })
        return ranking
    
    def get_author_profile(self, author: str) -> Dict:
        """作者画像"""
        papers = []
        coauthors = self.coauthor_network.get(author, [])
        for pid, paper in self.papers.items():
            if author in paper["authors"]:
                papers.append(paper["title"])
        return {
            "name": author,
            "paper_count": len(papers),
            "papers": papers,
            "coauthors": coauthors,
            "total_citations": sum(
                self.papers[pid]["citations"]
                for pid, p in self.papers.items()
                if author in p["authors"]
            ),
        }
    
    def get_policy_landscape(self) -> List[Dict]:
        """政策全景"""
        return [
            {"name": p["name"], "year": p["year"], 
             "type": p["type"], "related_topics": p["related_topics"]}
            for pcode, p in self.policies.items()
        ]
    
    def get_前沿趋势(self) -> Dict:
        """前沿识别（模拟突现检测）"""
        # 模拟：哪些主题正在快速升温
        return {
            "emerging_topics": [
                {"topic": "AI与知识服务", "trend": "↑↑↑", "description": "大模型在文旅知识服务中的应用快速增长"},
                {"topic": "文化遗产数字化", "trend": "↑↑", "description": "数字技术赋能文化遗产保护持续升温"},
                {"topic": "可持续旅游", "trend": "↑", "description": "沙特、埃及等国推动绿色旅游发展"},
            ],
            "declining_topics": [
                {"topic": "旅游教育与科研", "trend": "→", "description": "基础研究趋于平稳"},
            ]
        }
    
    def term_alignment_query(self, term: str) -> Dict:
        """术语对齐查询"""
        if term in self.term_alignment:
            return {
                "source": term,
                "alignments": self.term_alignment[term],
            }
        # 反向查询
        for cn, aliases in self.term_alignment.items():
            if term in aliases.values():
                return {
                    "source": term,
                    "alignments": {"中文": cn, **{k: v for k, v in aliases.items() if v != term}}
                }
        return {"source": term, "error": "未找到对应术语"}
    
    def multi_hop_query(self, topic: str) -> Dict:
        """多跳推理查询（模拟 GraphRAG）"""
        # 第一跳：主题→文献
        related_papers = []
        for tname, info in self.topics.items():
            if topic in tname:
                related_papers.extend(info["papers"])
        
        # 第二跳：文献→作者→其他文献
        related_authors = set()
        for pid in related_papers:
            related_authors.update(self.papers[pid]["authors"])
        
        # 第三跳：作者→合作者→合作机构
        extended_authors = set(related_authors)
        for author in related_authors:
            extended_authors.update(self.coauthor_network.get(author, []))
        
        return {
            "query_topic": topic,
            "direct_papers": [self.papers[pid]["title"] for pid in related_papers],
            "core_authors": list(related_authors),
            "extended_network": list(extended_authors - related_authors),
            "related_policies": [
                p["name"] for pcode, p in self.policies.items()
                if topic in str(p["related_topics"])
            ],
        }


# ============================================================================
# 第二部分：知识世界环境
# ============================================================================

class KnowledgeWorld:
    """
    中阿文旅知识世界环境。
    
    相当于 World-in-World 论文中的 3D 场景，但这里是知识空间。
    智能体的"位置"是当前的研究焦点/查询意图。
    """
    
    def __init__(self, kb: SinoArabKnowledgeBase):
        self.kb = kb
        self.current_focus = None  # 当前研究焦点
        self.query_history = []
        self.result_history = []
        self.steps_taken = 0
        self.max_steps = 10
        
    def reset(self, initial_query: str):
        """重置环境：用户提出初始问题"""
        self.current_focus = initial_query
        self.query_history = [initial_query]
        self.result_history = []
        self.steps_taken = 0
        
    def get_observation(self) -> Dict:
        """
        获取当前知识状态观察。
        对应论文中的 o_t — 当前环境观察。
        """
        # 基于当前焦点，从知识库获取上下文
        context = {
            'focus': self.current_focus,
            'steps_taken': self.steps_taken,
            'query_history': self.query_history,
            'nearby_topics': self._get_nearby_topics(),
            'hot_topics': self.kb.get_topic_hotspots()[:3],
            'frontier': self.kb.get_前沿趋势(),
        }
        return context
    
    def _get_nearby_topics(self) -> List[str]:
        """获取与当前焦点相关的主题"""
        related = []
        for topic in self.kb.topics:
            if self.current_focus and (
                self.current_focus in topic or 
                any(c in topic for c in self.current_focus)
            ):
                related.append(topic)
        if not related:
            related = list(self.kb.topics.keys())[:3]
        return related
    
    def execute_action(self, action: str, params: Optional[Dict] = None) -> Dict:
        """
        执行知识操作。
        对应论文中的环境交互：执行决策 D*_t。
        """
        if params is None:
            params = {}
        
        result = {"action": action, "params": params, "success": True}
        
        if action == "检索文献":
            query = params.get("query", self.current_focus)
            lang = params.get("lang", "全部")
            papers = self.kb.search(query, lang)
            result["output"] = papers
            self.current_focus = query
            
        elif action == "分析主题热度":
            hotspots = self.kb.get_topic_hotspots()
            result["output"] = hotspots
            self.current_focus = "主题热度分析"
            
        elif action == "识别研究前沿":
            frontier = self.kb.get_前沿趋势()
            result["output"] = frontier
            self.current_focus = "研究前沿识别"
            
        elif action == "作者画像":
            author = params.get("author", "张明")
            profile = self.kb.get_author_profile(author)
            result["output"] = profile
            self.current_focus = f"作者: {author}"
            
        elif action == "机构排名":
            ranking = self.kb.get_institution_ranking()
            result["output"] = ranking
            self.current_focus = "机构竞争力分析"
            
        elif action == "术语对齐":
            term = params.get("term", "文化遗产")
            alignment = self.kb.term_alignment_query(term)
            result["output"] = alignment
            self.current_focus = f"术语: {term}"
            
        elif action == "多跳推理":
            topic = params.get("topic", self.current_focus)
            hops = self.kb.multi_hop_query(topic)
            result["output"] = hops
            self.current_focus = topic
            
        elif action == "政策全景":
            policies = self.kb.get_policy_landscape()
            result["output"] = policies
            self.current_focus = "政策分析"
            
        elif action == "生成学科报告":
            report = self._generate_report()
            result["output"] = report
            self.current_focus = "学科报告"
            
        elif action == "沉淀到知识库":
            note = params.get("note", "服务记录")
            result["output"] = {"message": f"已沉淀服务记录: {note}", "沉淀类型": "服务案例"}
            # 对应论文中的「知识沉淀」
            
        else:
            result["success"] = False
            result["error"] = f"未知操作: {action}"
        
        self.query_history.append(self.current_focus)
        self.result_history.append(result)
        self.steps_taken += 1
        
        return result
    
    def _generate_report(self) -> Dict:
        """模拟生成学科服务报告"""
        hotspots = self.kb.get_topic_hotspots()
        frontier = self.kb.get_前沿趋势()
        ranking = self.kb.get_institution_ranking()
        
        report = {
            "标题": "中阿文旅研究动态周报",
            "生成时间": "2026年7月",
            "热点主题TOP3": [
                f"{h['topic']} (热度: {h['heat']})" for h in hotspots[:3]
            ],
            "新兴前沿": [
                f"{f['topic']} {f['trend']}: {f['description']}" 
                for f in frontier["emerging_topics"]
            ],
            "核心机构": [
                f"{r['name']} ({r['country']}, {r['paper_count']}篇)"
                for r in ranking[:3]
            ],
            "相关政策": [
                p["name"] for p in self.kb.get_policy_landscape()
            ],
            "推荐行动": [
                "重点关注AI赋能文旅知识服务的交叉研究",
                "加强与开罗大学、阿联酋大学的机构合作",
                "跟踪沙特2030愿景中的文旅投资动态",
            ],
        }
        return report
    
    def is_goal_reached(self, goal: Dict) -> bool:
        """
        判断是否完成用户需求。
        对应论文中的任务成功判断。
        """
        goal_type = goal.get("type", "")
        target = goal.get("target", "")
        
        if goal_type == "文献发现":
            return any(
                r.get("action") == "检索文献" and 
                any(target.lower() in str(p["paper"]["title"]).lower()
                    for p in r.get("output", []) if isinstance(r.get("output"), list))
                for r in self.result_history
            )
        elif goal_type == "热点分析":
            return any(r.get("action") == "分析主题热度" for r in self.result_history)
        elif goal_type == "前沿识别":
            return any(r.get("action") == "识别研究前沿" for r in self.result_history)
        elif goal_type == "术语查询":
            return any(r.get("action") == "术语对齐" for r in self.result_history)
        elif goal_type == "多跳分析":
            return any(r.get("action") == "多跳推理" for r in self.result_history)
        elif goal_type == "综合服务":
            # 需要完成多个子任务
            return self.steps_taken >= 3
        return False
    
    def is_done(self) -> bool:
        return self.steps_taken >= self.max_steps


# ============================================================================
# 第三部分：提案策略（π_proposal）
# ============================================================================

class KnowledgeProposalPolicy:
    """
    知识操作提案策略。
    
    根据当前研究焦点的上下文，提出候选知识操作序列。
    对应论文公式：Â_t^(m) ~ π_proposal(A | o_t, g)
    """
    
    def __init__(self, kb: SinoArabKnowledgeBase):
        self.kb = kb
        self.available_actions = [
            "检索文献", "分析主题热度", "识别研究前沿", 
            "作者画像", "机构排名", "术语对齐",
            "多跳推理", "政策全景", "生成学科报告",
        ]
    
    def propose_plans(self, obs: Dict, goal: Dict, 
                      horizon: int = 3, num_plans: int = 5) -> List[List[str]]:
        """
        生成 M 个候选知识操作计划。
        
        策略逻辑（模拟 VLM 的推理能力）：
        - 如果用户要"找文献"，优先提案检索类操作
        - 如果用户要"分析趋势"，优先提案计量类操作
        - 如果包含多语种需求，加入术语对齐
        """
        plans = []
        goal_type = goal.get("type", "综合服务")
        goal_target = goal.get("target", "")
        
        # 根据目标类型，构建有偏好的操作池
        if goal_type == "文献发现":
            preferred = ["检索文献", "多跳推理", "术语对齐", "检索文献", "作者画像"]
        elif goal_type == "热点分析":
            preferred = ["分析主题热度", "识别研究前沿", "多跳推理", "机构排名", "生成学科报告"]
        elif goal_type == "前沿识别":
            preferred = ["识别研究前沿", "分析主题热度", "多跳推理", "政策全景", "生成学科报告"]
        elif goal_type == "术语查询":
            preferred = ["术语对齐", "检索文献", "多跳推理", "检索文献", "术语对齐"]
        elif goal_type == "综合服务":
            preferred = ["分析主题热度", "识别研究前沿", "检索文献", "多跳推理", "生成学科报告"]
        else:
            preferred = self.available_actions.copy()
        
        for m in range(num_plans):
            plan = []
            # 第一步尽量从偏好的操作中选
            if m < len(preferred):
                plan.append(preferred[m])
            else:
                plan.append(random.choice(self.available_actions))
            
            # 后续步骤：根据前一步结果智能选择下一步
            for h in range(1, horizon):
                last_action = plan[-1]
                next_actions = self._suggest_next_action(last_action, goal_type)
                plan.append(next_actions[h % len(next_actions)] if next_actions else random.choice(self.available_actions))
            
            # 加入一些随机探索（多样性）
            if random.random() < 0.3:
                plan[-1] = random.choice(self.available_actions)
            
            plans.append(plan)
        
        return plans
    
    def _suggest_next_action(self, last_action: str, goal_type: str) -> List[str]:
        """根据上一步操作，建议下一步操作"""
        suggestions = {
            "检索文献": ["多跳推理", "作者画像", "术语对齐", "分析主题热度", "政策全景"],
            "分析主题热度": ["识别研究前沿", "多跳推理", "机构排名", "生成学科报告", "检索文献"],
            "识别研究前沿": ["分析主题热度", "多跳推理", "政策全景", "生成学科报告", "检索文献"],
            "作者画像": ["检索文献", "多跳推理", "机构排名", "分析主题热度", "术语对齐"],
            "机构排名": ["分析主题热度", "作者画像", "多跳推理", "检索文献", "生成学科报告"],
            "术语对齐": ["检索文献", "多跳推理", "分析主题热度", "政策全景", "作者画像"],
            "多跳推理": ["生成学科报告", "检索文献", "分析主题热度", "识别研究前沿", "政策全景"],
            "政策全景": ["多跳推理", "分析主题热度", "识别研究前沿", "生成学科报告", "检索文献"],
            "生成学科报告": ["沉淀到知识库", "检索文献", "多跳推理", "分析主题热度", "识别研究前沿"],
        }
        return suggestions.get(last_action, self.available_actions)


# ============================================================================
# 第四部分：知识世界模型（g_θ）
# ============================================================================

class KnowledgeWorldModel:
    """
    知识世界模型。
    
    在完整论文中，这对应 Stable Video Diffusion 等视频生成模型。
    在这里，它用知识图谱推理 + GraphRAG 来"预测"执行某个知识操作后
    会得到什么样的结果。
    
    核心功能：给定当前知识状态和候选操作，预测未来的知识状态。
    对应论文公式：Ô_t^(m) ~ g_θ(O | o_t, I_t^(m))
    """
    
    def __init__(self, kb: SinoArabKnowledgeBase, noise_level: float = 0.1):
        self.kb = kb
        self.noise_level = noise_level  # 模拟预测的不完美性
        
    def simulate(self, obs: Dict, plan: List[str]) -> List[Dict]:
        """
        模拟执行一个知识操作计划，预测每一步的结果。
        
        参数:
            obs: 当前知识状态观察 o_t
            plan: 候选操作计划 Â_t^(m)
            
        返回:
            预测的未来知识状态序列 Ô_t^(m)
        """
        simulated_states = []
        # 从当前焦点出发，模拟每一步
        current_focus = obs.get('focus', '中阿文旅')
        
        for action in plan:
            # 根据操作类型和当前焦点，预测结果
            simulated_state = self._predict_action_result(action, current_focus)
            simulated_states.append(simulated_state)
            
            # 更新预测的焦点
            if 'new_focus' in simulated_state:
                current_focus = simulated_state['new_focus']
            
            # 模拟预测噪声（世界模型的不完美性）
            if random.random() < self.noise_level:
                # 有时预测结果和实际会有偏差
                simulated_state['prediction_quality'] = 'low'
                simulated_state['warning'] = '预测可信度较低，建议馆员人工核查'
            else:
                simulated_state['prediction_quality'] = 'high'
        
        return simulated_states
    
    def _predict_action_result(self, action: str, focus: str) -> Dict:
        """预测单个操作的结果"""
        
        if action == "检索文献":
            # 预测搜索结果：会找到与焦点相关的文献
            papers = self.kb.search(focus, max_results=3)
            return {
                "action": action,
                "predicted_output": f"预计检索到 {len(papers)} 篇相关文献",
                "sample_results": [p["paper"]["title"] for p in papers],
                "new_focus": focus,
                "confidence": 0.85,
            }
        
        elif action == "分析主题热度":
            hotspots = self.kb.get_topic_hotspots()[:3]
            return {
                "action": action,
                "predicted_output": "将生成主题热度排名和趋势图",
                "top_predictions": [h["topic"] for h in hotspots],
                "new_focus": "主题热度分析",
                "confidence": 0.90,
            }
        
        elif action == "识别研究前沿":
            frontier = self.kb.get_前沿趋势()
            return {
                "action": action,
                "predicted_output": "将识别新兴前沿和衰退主题",
                "emerging": [f["topic"] for f in frontier["emerging_topics"]],
                "new_focus": "研究前沿识别",
                "confidence": 0.75,
            }
        
        elif action == "作者画像":
            # 预测会返回哪位作者的画像
            top_authors = ["张明", "李华", "王芳", "Chen Wei", "Ahmed Hassan"]
            author = random.choice(top_authors)
            profile = self.kb.get_author_profile(author)
            return {
                "action": action,
                "predicted_output": f"将生成作者「{author}」的学术画像",
                "author": author,
                "paper_count": profile["paper_count"],
                "new_focus": f"作者: {author}",
                "confidence": 0.80,
            }
        
        elif action == "术语对齐":
            terms = list(self.kb.term_alignment.keys())
            term = random.choice(terms)
            alignment = self.kb.term_alignment_query(term)
            return {
                "action": action,
                "predicted_output": f"将查询术语「{term}」的中阿英对齐",
                "alignments": alignment.get("alignments", {}),
                "new_focus": f"术语: {term}",
                "confidence": 0.95,
            }
        
        elif action == "多跳推理":
            return {
                "action": action,
                "predicted_output": f"将从「{focus}」出发进行多跳推理",
                "hops": 3,
                "new_focus": focus,
                "confidence": 0.70,
            }
        
        elif action == "生成学科报告":
            return {
                "action": action,
                "predicted_output": "将生成结构化学科服务报告",
                "report_sections": ["热点主题", "新兴前沿", "核心机构", "政策动态", "推荐行动"],
                "new_focus": "学科报告",
                "confidence": 0.85,
            }
        
        elif action == "沉淀到知识库":
            return {
                "action": action,
                "predicted_output": "将当前服务记录沉淀到 Obsidian 知识库",
                "new_focus": focus,
                "confidence": 0.95,
            }
        
        else:
            return {
                "action": action,
                "predicted_output": f"执行操作: {action}",
                "new_focus": focus,
                "confidence": 0.50,
            }


# ============================================================================
# 第五部分：修正策略（π_revision）
# ============================================================================

class KnowledgeRevisionPolicy:
    """
    知识修正策略：评估所有候选操作计划，选择最优的。
    
    对应论文：
        m* = arg max S(Â_t^(m), Ô_t^(m) | o_t, g)
        D_t* = Â_t^(m*)
    
    S 是评分函数，衡量预测结果与用户需求的契合度。
    """
    
    def evaluate_plans(self, obs: Dict, plans: List[List[str]],
                       simulated_futures: List[List[Dict]],
                       goal: Dict) -> Tuple[int, List[str], List[float]]:
        """
        评估所有候选计划。
        """
        scores = []
        
        for i, (plan, future) in enumerate(zip(plans, simulated_futures)):
            score = self._score_plan(obs, plan, future, goal)
            scores.append(score)
        
        best_idx = int(np.argmax(scores))
        return best_idx, plans[best_idx], scores
    
    def _score_plan(self, obs: Dict, plan: List[str], 
                    future: List[Dict], goal: Dict) -> float:
        """
        评分函数：
        - 操作类型与目标类型的匹配度
        - 预测结果的置信度
        - 操作的多样性（避免重复）
        - 覆盖的操作种类数
        """
        goal_type = goal.get("type", "综合服务")
        
        # 1. 目标匹配度
        action_goal_map = {
            "文献发现": ["检索文献", "多跳推理", "术语对齐"],
            "热点分析": ["分析主题热度", "多跳推理", "机构排名"],
            "前沿识别": ["识别研究前沿", "分析主题热度", "多跳推理"],
            "术语查询": ["术语对齐", "检索文献"],
            "多跳分析": ["多跳推理", "检索文献", "作者画像"],
            "综合服务": list(set(
                ["分析主题热度", "检索文献", "识别研究前沿", "术语对齐", 
                 "多跳推理", "政策全景", "生成学科报告"]
            )),
        }
        
        preferred = action_goal_map.get(goal_type, [])
        match_score = sum(3 for a in plan if a in preferred)
        
        # 2. 置信度评分
        confidence_scores = [s.get("confidence", 0.5) for s in future]
        conf_score = np.mean(confidence_scores) * 5
        
        # 3. 多样化奖励
        unique_actions = len(set(plan))
        diversity_score = unique_actions * 2
        
        # 4. 覆盖度的奖励
        covered = len(set(preferred) & set(plan))
        coverage_score = (covered / max(len(preferred), 1)) * 5
        
        # 5. 以"生成学科报告"或"沉淀到知识库"结尾加分（完成闭环）
        final_bonus = 0
        if plan[-1] == "生成学科报告":
            final_bonus += 3
        if plan[-1] == "沉淀到知识库":
            final_bonus += 2
        
        return match_score + conf_score + diversity_score + coverage_score + final_bonus


# ============================================================================
# 第六部分：闭循环规划器
# ============================================================================

class SinoArabWorldPlanner:
    """
    中阿文旅科学知识世界模型规划器。
    
    对应 World-in-World 论文 Figure 3 的完整架构：
    提案(❶) → 统一动作API(❷) → 世界模型模拟(❸) → 修正(❹) → 执行
    """
    
    def __init__(self, 
                 proposal_policy: KnowledgeProposalPolicy,
                 world_model: KnowledgeWorldModel,
                 revision_policy: KnowledgeRevisionPolicy,
                 env: KnowledgeWorld,
                 num_candidates: int = 5,
                 horizon: int = 4):
        
        self.proposal_policy = proposal_policy
        self.world_model = world_model
        self.revision_policy = revision_policy
        self.env = env
        self.M = num_candidates
        self.L = horizon
        
        self.plan_history = []
        self.score_history = []
    
    def run_episode(self, initial_query: str, goal: Dict,
                    verbose: bool = True) -> Dict:
        """
        运行完整的闭循环知识服务回合。
        """
        self.env.reset(initial_query)
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"👤 用户需求: {goal.get('description', initial_query)}")
            print(f"🎯 目标类型: {goal.get('type', '综合服务')}")
            print(f"{'='*60}")
        
        step = 0
        while not self.env.is_done() and not self.env.is_goal_reached(goal):
            obs = self.env.get_observation()
            
            if verbose:
                print(f"\n{'─'*50}")
                print(f"📌 第 {step+1} 步 — 当前研究焦点: 「{obs['focus']}」")
                
                # 显示当前知识世界状态概览
                top_str = ' | '.join(
                    f'{t["topic"]}(热度{t["heat"]})' 
                    for t in obs['hot_topics'][:3]
                )
                print(f'  热点主题TOP: {top_str}')
                print(f"  邻近主题: {', '.join(obs['nearby_topics'][:3])}")
                print(f"  新兴前沿: {obs['frontier']['emerging_topics'][0]['topic'] if obs['frontier']['emerging_topics'] else '—'}")
            
            # ====== ❶ 提案阶段 ======
            candidates = self.proposal_policy.propose_plans(
                obs, goal, horizon=self.L, num_plans=self.M
            )
            
            if verbose:
                print(f"\n── 提案阶段：生成 {self.M} 个候选知识服务计划 ──")
                for i, plan in enumerate(candidates):
                    print(f"  计划 {i}: {' → '.join(plan)}")
            
            # ====== ❷ 统一动作 API（动作转换） ======
            # 在此简化版中，操作名直接是 API 调用名
            # 完整实现中，这里会将操作转为：文本提示 / API 参数 / 低层调用
            
            # ====== ❸ 世界模型模拟 ======
            simulated_futures = []
            for plan in candidates:
                future = self.world_model.simulate(obs, plan)
                simulated_futures.append(future)
            
            if verbose:
                print(f"\n── 模拟阶段：对每个计划预测服务结果 ──")
                for i, future in enumerate(simulated_futures):
                    predictions = [f['predicted_output'][:40]+'...' 
                                   if len(f.get('predicted_output',''))>40 
                                   else f.get('predicted_output','') 
                                   for f in future]
                    quality = future[0].get('prediction_quality', 'high')
                    print(f"  计划 {i}: {' → '.join(predictions)} [可信度:{quality}]")
            
            # ====== ❹ 修正阶段 ======
            best_idx, best_plan, scores = self.revision_policy.evaluate_plans(
                obs, candidates, simulated_futures, goal
            )
            
            self.plan_history.append(best_plan)
            self.score_history.append(scores)
            
            if verbose:
                print(f"\n── 修正阶段：评分并选择最优计划 ──")
                for i, s in enumerate(scores):
                    marker = " ← 最优" if i == best_idx else ""
                    print(f"  计划 {i} 评分: {s:.1f}{marker}")
                print(f"\n  ✅ 选中计划: {' → '.join(best_plan)}")
            
            # ====== 执行计划的第一步 ======
            first_action = best_plan[0]
            action_params = self._get_action_params(first_action, obs, goal)
            
            if verbose:
                print(f"\n── 执行操作: {first_action} ──")
            
            result = self.env.execute_action(first_action, action_params)
            
            if verbose:
                output = result.get('output', {})
                if isinstance(output, list) and len(output) > 0:
                    if 'paper' in output[0]:
                        print(f"  检索到 {len(output)} 篇文献:")
                        for p in output[:3]:
                            print(f"    📄 {p['paper']['title']} ({p['paper']['year']})")
                    elif 'topic' in output[0]:
                        print(f"  主题热度排名:")
                        for h in output[:3]:
                            print(f"    🔥 {h['topic']}: 热度 {h['heat']}, {h['paper_count']}篇文献")
                    else:
                        print(f"  输出: {str(output)[:100]}...")
                elif isinstance(output, dict):
                    if '报告' in str(output):
                        print(f"  📊 报告已生成，包含 {len(output)} 个板块")
                    elif 'message' in output:
                        print(f"  💾 {output['message']}")
                    else:
                        print(f"  输出: {str(output)[:100]}...")
                else:
                    print(f"  ✅ 操作完成")
                
                print(f"  新研究焦点: 「{self.env.current_focus}」")
            
            step += 1
        
        # 回合结束
        success = self.env.is_goal_reached(goal)
        
        if verbose:
            print(f"\n{'='*60}")
            if success:
                print(f"🎉 知识服务任务完成！共 {self.env.steps_taken} 步")
            else:
                print(f"⏰ 服务结束（已用 {self.env.steps_taken} 步）")
            print(f"   研究轨迹: {self.env.query_history}")
        
        return {
            'success': success,
            'steps': self.env.steps_taken,
            'query_history': self.env.query_history,
            'result_history': self.env.result_history,
            'goal': goal,
        }
    
    def _get_action_params(self, action: str, obs: Dict, goal: Dict) -> Dict:
        """根据操作类型和上下文，生成执行参数"""
        params = {}
        
        if action == "检索文献":
            params["query"] = obs.get('focus', '中阿文旅')
            # 如果目标中指定了语言
            if 'lang' in goal:
                params["lang"] = goal['lang']
        
        elif action == "作者画像":
            # 从热点主题中选一个代表性作者
            top_authors = ["张明", "李华", "王芳", "Chen Wei", "Ahmed Hassan"]
            params["author"] = random.choice(top_authors)
        
        elif action == "术语对齐":
            terms = list(self.env.kb.term_alignment.keys())
            params["term"] = random.choice(terms)
        
        elif action == "多跳推理":
            params["topic"] = obs.get('focus', '中阿文旅')
        
        elif action == "生成学科报告":
            params["format"] = "周报"
        
        elif action == "沉淀到知识库":
            params["note"] = f"服务记录: {obs.get('focus', '')} - {self.env.steps_taken + 1}"
        
        return params


# ============================================================================
# 第七部分：评估和对比实验
# ============================================================================

def evaluate_service(planner: SinoArabWorldPlanner, 
                     test_cases: List[Tuple[str, Dict]],
                     verbose: bool = False) -> Dict:
    """
    在多个服务场景上评估规划器。
    """
    successes = 0
    total_steps = []
    
    for query, goal in test_cases:
        result = planner.run_episode(query, goal, verbose=verbose)
        if result['success']:
            successes += 1
            total_steps.append(result['steps'])
    
    return {
        'success_rate': successes / len(test_cases) * 100,
        'avg_steps': np.mean(total_steps) if total_steps else 0,
        'total_cases': len(test_cases),
    }


# ============================================================================
# 第八部分：主程序
# ============================================================================

def main():
    print("=" * 70)
    print("🌍 中阿文旅科学知识世界模型")
    print("   基于 World-in-World 闭循环规划算法")
    print("   应用于高校图书馆智能学科服务")
    print("=" * 70)
    
    # ====== 初始化 ======
    kb = SinoArabKnowledgeBase()
    env = KnowledgeWorld(kb)
    
    print(f"\n📚 模拟中阿文旅知识库已初始化:")
    print(f"   • 文献: {len(kb.papers)} 篇 (中文/阿拉伯语/英文)")
    print(f"   • 主题: {len(kb.topics)} 个")
    print(f"   • 机构: {len(kb.institutions)} 所")
    print(f"   • 政策: {len(kb.policies)} 项")
    print(f"   • 项目: {len(kb.projects)} 项")
    print(f"   • 术语对齐: {len(kb.term_alignment)} 组")
    
    # ====== 演示场景 1：教师课题申报支持 ======
    print("\n\n" + "=" * 70)
    print("📋 场景一：教师课题申报支持")
    print("   用户需求：分析近五年中阿文化遗产旅游研究热点，推荐课题方向")
    print("=" * 70)
    
    proposal = KnowledgeProposalPolicy(kb)
    world_model = KnowledgeWorldModel(kb, noise_level=0.15)
    revision = KnowledgeRevisionPolicy()
    
    planner = SinoArabWorldPlanner(
        proposal_policy=proposal,
        world_model=world_model,
        revision_policy=revision,
        env=KnowledgeWorld(kb),
        num_candidates=5,
        horizon=4,
    )
    
    goal_1 = {
        "type": "热点分析",
        "target": "文化遗产",
        "description": "分析近五年中阿文化遗产旅游研究热点，推荐课题方向",
        "lang": "全部",
    }
    
    result_1 = planner.run_episode(
        "中阿文化遗产旅游",
        goal_1,
        verbose=True
    )
    
    # ====== 演示场景 2：多语种文献检索 ======
    print("\n\n" + "=" * 70)
    print("📋 场景二：跨语言文献发现与术语对齐")
    print("   用户需求：查找阿拉伯语文旅政策相关文献，并获取中阿术语对照")
    print("=" * 70)
    
    goal_2 = {
        "type": "文献发现",
        "target": "文旅政策",
        "description": "查找阿拉伯语文旅政策相关文献，获取术语对照",
        "lang": "阿拉伯语",
    }
    
    planner2 = SinoArabWorldPlanner(
        proposal_policy=KnowledgeProposalPolicy(kb),
        world_model=KnowledgeWorldModel(kb, noise_level=0.1),
        revision_policy=KnowledgeRevisionPolicy(),
        env=KnowledgeWorld(kb),
        num_candidates=5,
        horizon=3,
    )
    
    result_2 = planner2.run_episode(
        "السياحة والثقافة في الدول العربية",
        goal_2,
        verbose=True
    )
    
    # ====== 演示场景 3：学科服务周报生成 ======
    print("\n\n" + "=" * 70)
    print("📋 场景三：学科馆员智能服务 — 生成周报")
    print("   用户需求：生成本周中阿文旅学科服务周报")
    print("=" * 70)
    
    goal_3 = {
        "type": "综合服务",
        "target": "周报",
        "description": "生成本周中阿文旅学科服务周报",
    }
    
    planner3 = SinoArabWorldPlanner(
        proposal_policy=KnowledgeProposalPolicy(kb),
        world_model=KnowledgeWorldModel(kb, noise_level=0.05),
        revision_policy=KnowledgeRevisionPolicy(),
        env=KnowledgeWorld(kb),
        num_candidates=5,
        horizon=4,
    )
    
    result_3 = planner3.run_episode(
        "中阿文旅研究动态",
        goal_3,
        verbose=True
    )
    
    # ====== 验证论文三大发现在知识世界中的表现 ======
    print("\n\n" + "=" * 70)
    print("📊 验证：World-in-World 三大发现在知识世界中的表现")
    print("=" * 70)
    
    test_cases = [
        ("中阿文旅", {"type": "综合服务", "target": "综合", "description": "综合知识服务"}),
        ("文化遗产数字化", {"type": "热点分析", "target": "热点", "description": "热点分析"}),
        ("中阿旅游合作", {"type": "文献发现", "target": "旅游合作", "description": "文献发现"}),
        ("阿拉伯文旅政策", {"type": "前沿识别", "target": "前沿", "description": "前沿识别"}),
        ("中阿术语", {"type": "术语查询", "target": "术语", "description": "术语查询"}),
    ]
    
    # 发现①：可控性 vs 不可控性
    print(f'\n── 发现①：可控性比"画面质量"更重要 ──')
    
    for name, noise in [("高可控世界模型(噪声0.05)", 0.05),
                         ("中等可控(噪声0.30)", 0.30),
                         ("低可控(噪声0.60)", 0.60)]:
        wm = KnowledgeWorldModel(kb, noise_level=noise)
        p = SinoArabWorldPlanner(
            KnowledgeProposalPolicy(kb), wm, KnowledgeRevisionPolicy(),
            KnowledgeWorld(kb), 5, 3
        )
        stats = evaluate_service(p, test_cases, verbose=False)
        print(f"  {name}:")
        print(f"    服务成功率: {stats['success_rate']:.0f}%")
        print(f"    平均服务步数: {stats['avg_steps']:.1f}")
    
    # 发现③：推理时缩放
    print(f"\n── 发现③：多模拟几次（增大候选数M）效果更好 ──")
    
    for num_M in [1, 3, 8]:
        p = SinoArabWorldPlanner(
            KnowledgeProposalPolicy(kb), 
            KnowledgeWorldModel(kb, noise_level=0.1),
            KnowledgeRevisionPolicy(),
            KnowledgeWorld(kb),
            num_candidates=num_M,
            horizon=3,
        )
        stats = evaluate_service(p, test_cases, verbose=False)
        print(f"  候选计划数 M={num_M}:")
        print(f"    服务成功率: {stats['success_rate']:.0f}%")
        print(f"    平均步数: {stats['avg_steps']:.1f}")
    
    # ====== 全流程闭环总结 ======
    print("\n\n" + "=" * 70)
    print("🎯 总结：中阿文旅科学知识世界模型完整闭环")
    print("=" * 70)
    print("""
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   ① 资源采集                                        │
    │       ↓                                             │
    │   ② 知识组织 (知识图谱 + 术语库)                     │
    │       ↓                                             │
    │   ③ 状态感知 (科学计量 + 主题热度 + 前沿识别)        │
    │       ↓                                             │
    │   ④ 智能服务 (检索 + 分析 + 问答 + 报告 + 推送)     │
    │       ↓                                             │
    │   ⑤ 馆员审核 (来源追溯 + 质量校验 + 风险提示)        │
    │       ↓                                             │
    │   ⑥ 知识沉淀 (Obsidian + 图谱回写 + 服务案例复用)   │
    │       ↑_____________ 闭循环 _____________↓          │
    │                                                     │
    └─────────────────────────────────────────────────────┘
    
    对应挑战杯策划案的核心流程：
    资源采集 → 知识组织 → 状态感知 → 智能服务 → 馆员审核 → 知识沉淀
    
    下一阶段：
    - 将模拟知识库替换为真实的中阿文旅文献数据
    - 接入真实的 GraphRAG 和大模型智能体
    - 连接飞书和 Obsidian 实现服务闭环
    """)


if __name__ == "__main__":
    main()
