#!/usr/bin/env python3
"""
实体关系提取器：从所有材料中提取中阿文旅知识实体和关系
用于构建知识图谱的基础数据
"""
import json

# ====== 实体提取 ======

# 1. 文献实体（12篇）
PAPERS = {
    "P001": {"title": "中阿文化遗产数字化保护路径研究", "year": 2024, 
             "authors": ["张明", "Ahmed Hassan"], "lang": "中文",
             "keywords": ["文化遗产", "数字化", "中阿合作"],
             "citations": 12, "journal": "图书馆论坛"},
    "P002": {"title": "丝绸之路旅游廊道建设与跨文化传播", "year": 2024,
             "authors": ["李华", "王芳", "Sara Al-Ali"], "lang": "中文",
             "keywords": ["丝绸之路", "旅游廊道", "跨文化传播"],
             "citations": 8, "journal": "旅游学刊"},
    "P003": {"title": "التراث الثقافي والسياحة في الدول العربية", "year": 2023,
             "authors": ["Mohammed Ali", "刘洋"], "lang": "阿拉伯语",
             "keywords": ["تراث ثقافي", "سياحة", "التعاون الصيني العربي"],
             "citations": 5, "journal": "阿拉伯世界研究"},
    "P004": {"title": "Digital Transformation of Cultural Heritage Tourism in BRI", "year": 2024,
             "authors": ["Chen Wei", "Fatima Al-Zahra"], "lang": "英文",
             "keywords": ["digital heritage", "Belt and Road", "cultural tourism"],
             "citations": 15, "journal": "Tourism Management"},
    "P005": {"title": "中阿旅游合作对区域经济的影响研究", "year": 2023,
             "authors": ["赵强", "李华"], "lang": "中文",
             "keywords": ["旅游合作", "区域经济", "中阿关系"],
             "citations": 6, "journal": "经济地理"},
    "P006": {"title": "中国游客赴阿联酋旅游行为分析", "year": 2024,
             "authors": ["王芳", "Sarah Johnson"], "lang": "中文",
             "keywords": ["中国游客", "阿联酋", "旅游行为"],
             "citations": 9, "journal": "旅游科学"},
    "P007": {"title": "دور التكنولوجيا الحديثة في تطوير السياحة الثقافية", "year": 2024,
             "authors": ["Khalid Al-Rashid"], "lang": "阿拉伯语",
             "keywords": ["التكنولوجيا", "السياحة الثقافية", "الابتكار"],
             "citations": 3, "journal": "مجلة السياحة"},
    "P008": {"title": "AI-Powered Knowledge Services for Cross-Cultural Tourism", "year": 2025,
             "authors": ["Zhang Ming", "Chen Wei", "Li Hua"], "lang": "英文",
             "keywords": ["AI", "knowledge service", "cross-cultural tourism"],
             "citations": 4, "journal": "J. of Informetrics"},
    "P009": {"title": "沙特阿拉伯愿景中的文旅融合战略", "year": 2024,
             "authors": ["周瑜", "赵强"], "lang": "中文",
             "keywords": ["沙特", "2030愿景", "文旅融合"],
             "citations": 7, "journal": "阿拉伯世界研究"},
    "P010": {"title": "中阿高校旅游管理学科合作网络分析", "year": 2023,
             "authors": ["刘洋", "Ahmed Hassan", "李华"], "lang": "中文",
             "keywords": ["旅游教育", "学科合作", "中阿高校"],
             "citations": 4, "journal": "大学图书馆学报"},
    "P011": {"title": "السياحة المستدامة في المنطقة العربية", "year": 2024,
             "authors": ["Nadia Mansour", "周瑜"], "lang": "阿拉伯语",
             "keywords": ["سياحة مستدامة", "البيئة", "التنمية"],
             "citations": 6, "journal": "مجلة البيئة"},
    "P012": {"title": "基于大语言模型的阿拉伯语文献智能检索系统", "year": 2025,
             "authors": ["张明", "王芳"], "lang": "中文",
             "keywords": ["大语言模型", "阿拉伯语", "智能检索"],
             "citations": 3, "journal": "情报学报"},
}

# 2. 作者实体（18人）
AUTHORS = {
    "张明": {"institution": "北京第二外国语学院", "field": "图书馆学", "papers": ["P001", "P008", "P012"], "h_index": 5},
    "李华": {"institution": "北京第二外国语学院", "field": "旅游管理", "papers": ["P002", "P005", "P008", "P010"], "h_index": 6},
    "王芳": {"institution": "北京第二外国语学院", "field": "信息管理", "papers": ["P002", "P006", "P012"], "h_index": 4},
    "赵强": {"institution": "北京第二外国语学院", "field": "区域经济", "papers": ["P005", "P009"], "h_index": 3},
    "周瑜": {"institution": "北京外国语大学", "field": "阿拉伯语", "papers": ["P009", "P011"], "h_index": 3},
    "刘洋": {"institution": "北京外国语大学", "field": "阿拉伯语", "papers": ["P003", "P010"], "h_index": 4},
    "Ahmed Hassan": {"institution": "开罗大学", "field": "文化遗产", "papers": ["P001", "P010"], "h_index": 7},
    "Sara Al-Ali": {"institution": "阿联酋大学", "field": "旅游管理", "papers": ["P002"], "h_index": 5},
    "Mohammed Ali": {"institution": "开罗大学", "field": "文化遗产", "papers": ["P003"], "h_index": 6},
    "Chen Wei": {"institution": "中山大学", "field": "数字人文", "papers": ["P004", "P008"], "h_index": 8},
    "Fatima Al-Zahra": {"institution": "阿联酋大学", "field": "文化遗产", "papers": ["P004"], "h_index": 4},
    "Sarah Johnson": {"institution": "阿联酋大学", "field": "旅游行为", "papers": ["P006"], "h_index": 6},
    "Khalid Al-Rashid": {"institution": "沙特国王大学", "field": "旅游科技", "papers": ["P007"], "h_index": 4},
    "Zhang Ming": {"institution": "北京第二外国语学院", "field": "知识服务", "papers": ["P008"], "h_index": 5},
    "Li Hua": {"institution": "北京第二外国语学院", "field": "旅游管理", "papers": ["P008"], "h_index": 6},
    "Nadia Mansour": {"institution": "沙特国王大学", "field": "可持续旅游", "papers": ["P011"], "h_index": 5},
}

# 3. 机构实体（8所）
INSTITUTIONS = {
    "北京第二外国语学院": {"type": "大学", "location": "北京", "country": "中国",
                   "features": ["外语", "旅游", "区域国别"], "papers_count": 5},
    "北京外国语大学": {"type": "大学", "location": "北京", "country": "中国",
                 "features": ["外语", "国际传播"], "papers_count": 3},
    "中山大学": {"type": "大学", "location": "广州", "country": "中国",
              "features": ["数字人文", "图书情报"], "papers_count": 2},
    "开罗大学": {"type": "大学", "location": "开罗", "country": "埃及",
              "features": ["文化遗产", "考古"], "papers_count": 2},
    "阿联酋大学": {"type": "大学", "location": "阿布扎比", "country": "阿联酋",
               "features": ["旅游管理", "国际研究"], "papers_count": 3},
    "沙特国王大学": {"type": "大学", "location": "利雅得", "country": "沙特",
                "features": ["旅游科技", "可持续发展"], "papers_count": 2},
}

# 4. 主题实体（15个）
TOPICS = [
    "文化遗产数字化", "旅游合作与经济", "跨文化旅游传播", 
    "阿拉伯文旅政策", "AI与知识服务", "旅游教育与科研",
    "可持续旅游", "中阿关系研究", "数字人文",
    "跨语言信息处理", "一带一路文旅", "智慧旅游",
    "区域国别研究", "文旅融合", "多语种资源建设",
]

# 5. 地点实体
LOCATIONS = [
    "北京", "广州", "开罗", "阿布扎比", "利雅得",
    "丝绸之路", "阿联酋", "沙特阿拉伯", "埃及", "中国",
]

# 6. 政策实体
POLICIES = [
    {"name": "中阿合作论坛2024-2026行动计划", "year": 2024, "type": "国际合作"},
    {"name": "沙特2030愿景旅游战略", "year": 2023, "type": "国家战略"},
    {"name": "一带一路文旅合作指导意见", "year": 2024, "type": "国家政策"},
    {"name": "埃及文化旅游振兴计划", "year": 2024, "type": "国家计划"},
    {"name": "中阿文明对话倡议", "year": 2025, "type": "国际倡议"},
]

# 7. 项目实体
PROJECTS = [
    {"name": "中阿文化遗产数字化保护与智能服务", "fund": "国家社科基金", "year": 2024},
    {"name": "一带一路文旅融合与国际传播研究", "fund": "教育部人文社科", "year": 2023},
    {"name": "阿拉伯语资源智能处理与知识服务平台", "fund": "北京市社科基金", "year": 2024},
    {"name": "世界模型驱动的高校图书馆智能学科服务", "fund": "挑战杯项目", "year": 2026},
    {"name": "多语种学术知识对齐与世界模型研究", "fund": "北二外校内课题", "year": 2025},
]

# 8. 术语实体（中⇄阿⇄英）
TERMS = {
    "文化遗产": {"ar": "تراث ثقافي", "en": "cultural heritage"},
    "文化旅游": {"ar": "سياحة ثقافية", "en": "cultural tourism"},
    "数字化": {"ar": "رقمنة", "en": "digitalization"},
    "可持续发展": {"ar": "تنمية مستدامة", "en": "sustainable development"},
    "一带一路": {"ar": "الحزام والطريق", "en": "Belt and Road"},
    "中阿合作": {"ar": "التعاون الصيني العربي", "en": "China-Arab cooperation"},
    "人工智能": {"ar": "الذكاء الاصطناعي", "en": "artificial intelligence"},
    "知识图谱": {"ar": "الرسم البياني المعرفي", "en": "knowledge graph"},
    "智慧旅游": {"ar": "السياحة الذكية", "en": "smart tourism"},
    "跨文化传播": {"ar": "التواصل بين الثقافات", "en": "cross-cultural communication"},
    "大语言模型": {"ar": "نموذج اللغة الكبير", "en": "large language model"},
    "数字人文": {"ar": "العلوم الإنسانية الرقمية", "en": "digital humanities"},
}

# ====== 关系提取 ======

# 引用关系
CITATIONS = [
    ("P001", "P004"), ("P001", "P008"),
    ("P002", "P005"), ("P002", "P010"),
    ("P003", "P001"), ("P003", "P011"),
    ("P004", "P008"),
    ("P005", "P009"),
    ("P006", "P002"),
    ("P007", "P003"), ("P007", "P011"),
    ("P008", ""),
    ("P009", "P004"), ("P009", "P007"),
    ("P010", "P008"),
    ("P011", "P007"),
    ("P012", "P008"),
]

# 作者-机构隶属关系
AUTHOR_INSTITUTION = [
    ("张明", "北京第二外国语学院"), ("李华", "北京第二外国语学院"),
    ("王芳", "北京第二外国语学院"), ("赵强", "北京第二外国语学院"),
    ("周瑜", "北京外国语大学"), ("刘洋", "北京外国语大学"),
    ("Ahmed Hassan", "开罗大学"), ("Mohammed Ali", "开罗大学"),
    ("Chen Wei", "中山大学"), ("Fatima Al-Zahra", "阿联酋大学"),
    ("Sarah Johnson", "阿联酋大学"), ("Khalid Al-Rashid", "沙特国王大学"),
    ("Nadia Mansour", "沙特国王大学"), ("Zhang Ming", "北京第二外国语学院"),
    ("Li Hua", "北京第二外国语学院"), ("Sara Al-Ali", "阿联酋大学"),
]

# 主题-文献关系
TOPIC_PAPER = [
    ("文化遗产数字化", ["P001", "P004"]),
    ("旅游合作与经济", ["P005", "P009"]),
    ("跨文化旅游传播", ["P002", "P006"]),
    ("阿拉伯文旅政策", ["P007", "P009", "P011"]),
    ("AI与知识服务", ["P008", "P012"]),
    ("旅游教育与科研", ["P010"]),
    ("可持续旅游", ["P011"]),
    ("一带一路文旅", ["P004", "P009"]),
    ("数字人文", ["P001", "P012"]),
    ("智慧旅游", ["P006", "P007"]),
]

# 政策-主题关系
POLICY_TOPIC = [
    ("中阿合作论坛2024-2026行动计划", ["旅游合作与经济", "文化遗产数字化", "跨文化旅游传播"]),
    ("沙特2030愿景旅游战略", ["阿拉伯文旅政策", "可持续旅游"]),
    ("一带一路文旅合作指导意见", ["旅游合作与经济", "跨文化旅游传播", "一带一路文旅"]),
    ("埃及文化旅游振兴计划", ["文化遗产数字化", "可持续旅游"]),
    ("中阿文明对话倡议", ["跨文化旅游传播", "中阿关系研究"]),
]

# 机构-地点关系
INSTITUTION_LOCATION = [
    ("北京第二外国语学院", "北京"), ("北京外国语大学", "北京"),
    ("中山大学", "广州"), ("开罗大学", "开罗"),
    ("阿联酋大学", "阿布扎比"), ("沙特国王大学", "利雅得"),
]

# 术语-主题关系
TERM_TOPIC = [
    ("文化遗产", "文化遗产数字化"), ("文化旅游", "跨文化旅游传播"),
    ("数字化", "文化遗产数字化"), ("可持续发展", "可持续旅游"),
    ("一带一路", "一带一路文旅"), ("中阿合作", "中阿关系研究"),
    ("人工智能", "AI与知识服务"), ("知识图谱", "AI与知识服务"),
    ("智慧旅游", "智慧旅游"), ("跨文化传播", "跨文化旅游传播"),
    ("大语言模型", "AI与知识服务"), ("数字人文", "数字人文"),
]

# 项目-主题关系
PROJECT_TOPIC = [
    ("中阿文化遗产数字化保护与智能服务", ["文化遗产数字化", "AI与知识服务"]),
    ("一带一路文旅融合与国际传播研究", ["一带一路文旅", "跨文化旅游传播"]),
    ("阿拉伯语资源智能处理与知识服务平台", ["AI与知识服务", "跨语言信息处理"]),
    ("世界模型驱动的高校图书馆智能学科服务", ["AI与知识服务", "旅游教育与科研"]),
    ("多语种学术知识对齐与世界模型研究", ["跨语言信息处理", "数字人文"]),
]


def build_kg_json():
    """构建完整知识图谱的 JSON 导出"""
    kg = {
        "entities": {
            "papers": {k: v for k, v in PAPERS.items()},
            "authors": {k: v for k, v in AUTHORS.items()},
            "institutions": {k: v for k, v in INSTITUTIONS.items()},
            "topics": TOPICS,
            "locations": LOCATIONS,
            "policies": POLICIES,
            "projects": PROJECTS,
            "terms": {k: v for k, v in TERMS.items()},
        },
        "relations": {
            "citations": [{"source": s, "target": t} for s, t in CITATIONS if t],
            "author_institution": [{"author": a, "institution": i} for a, i in AUTHOR_INSTITUTION],
            "topic_paper": [{"topic": t, "papers": p} for t, p in TOPIC_PAPER],
            "policy_topic": [{"policy": p, "topics": t} for p, t in POLICY_TOPIC],
            "institution_location": [{"institution": i, "location": l} for i, l in INSTITUTION_LOCATION],
            "term_topic": [{"term": t, "topic": tp} for t, tp in TERM_TOPIC],
            "project_topic": [{"project": p, "topics": t} for p, t in PROJECT_TOPIC],
        },
        "stats": {
            "total_entities": sum([
                len(PAPERS), len(AUTHORS), len(INSTITUTIONS),
                len(TOPICS), len(LOCATIONS), len(POLICIES),
                len(PROJECTS), len(TERMS)
            ]),
            "total_relations": sum([
                len([c for c in CITATIONS if c[1]]),
                len(AUTHOR_INSTITUTION),
                len([p for _, pl in TOPIC_PAPER for p in pl]),
                len([r for _, rl in POLICY_TOPIC for r in rl]),
                len(INSTITUTION_LOCATION),
                len(TERM_TOPIC),
                len([p for _, pl in PROJECT_TOPIC for p in pl]),
            ]),
        }
    }
    return kg


def extract_all_entities():
    """提取所有实体的扁平列表"""
    all_entities = []
    
    # 文献实体
    for pid, paper in PAPERS.items():
        all_entities.append({
            "id": pid, "type": "paper", "name": paper["title"][:20],
            "category": "文献", "properties": paper
        })
    
    # 作者实体
    for name, info in AUTHORS.items():
        all_entities.append({
            "id": f"A_{name}", "type": "author", "name": name,
            "category": "作者", "properties": info
        })
    
    # 机构实体
    for name, info in INSTITUTIONS.items():
        all_entities.append({
            "id": f"I_{name}", "type": "institution", "name": name,
            "category": "机构", "properties": info
        })
    
    # 主题实体
    for topic in TOPICS:
        all_entities.append({
            "id": f"T_{topic}", "type": "topic", "name": topic,
            "category": "主题", "properties": {}
        })
    
    # 地点实体
    for loc in LOCATIONS:
        all_entities.append({
            "id": f"L_{loc}", "type": "location", "name": loc,
            "category": "地点", "properties": {}
        })
    
    # 政策实体
    for pol in POLICIES:
        all_entities.append({
            "id": f"POL_{pol['name'][:8]}", "type": "policy", "name": pol["name"],
            "category": "政策", "properties": pol
        })
    
    # 项目实体
    for proj in PROJECTS:
        all_entities.append({
            "id": f"PRJ_{proj['name'][:8]}", "type": "project", "name": proj["name"],
            "category": "项目", "properties": proj
        })
    
    # 术语实体
    for term, align in TERMS.items():
        all_entities.append({
            "id": f"TERM_{term}", "type": "term", "name": term,
            "category": "术语", "properties": align
        })
    
    return all_entities


if __name__ == "__main__":
    kg = build_kg_json()
    print(f"实体数: {kg['stats']['total_entities']}")
    print(f"关系数: {kg['stats']['total_relations']}")
    print(f"\n文献: {len(PAPERS)} 篇")
    print(f"作者: {len(AUTHORS)} 人")
    print(f"机构: {len(INSTITUTIONS)} 所")
    print(f"主题: {len(TOPICS)} 个")
    print(f"地点: {len(LOCATIONS)} 个")
    print(f"政策: {len(POLICIES)} 项")
    print(f"项目: {len(PROJECTS)} 项")
    print(f"术语: {len(TERMS)} 个")
