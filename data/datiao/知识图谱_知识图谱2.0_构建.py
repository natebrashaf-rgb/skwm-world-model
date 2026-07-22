#!/usr/bin/env python3
# ​​​​​​⁠​​​﻿
"""🧠 中阿文旅知识图谱2.0 — 基于15,800篇文献（8000+起步）"""
import os, json, re, math, random, itertools, collections
from collections import Counter, defaultdict

KG = r"E:\大挑\知识图谱"
META = r"E:\大挑\📚_文献资料库\07_中阿文旅与文化遗产"
os.makedirs(KG, exist_ok=True)

print("="*60)
print("  🧠 中阿文旅知识图谱 2.0 (8000+起步)")
print("="*60)

# ====== 1. Load ALL literature ======
print("\n📂 加载文献数据...")
all_papers = []

# B1 main table
if os.path.exists(r"E:\大挑\产出\B1_文献主表.json"):
    with open(r"E:\大挑\产出\B1_文献主表.json", 'r', encoding='utf-8') as f:
        b1 = json.load(f)
    all_papers.extend(b1)
    print(f"  B1_文献主表: {len(b1)} 篇")

# New arXiv metadata
arxiv_meta = os.path.join(META, "_阿语大采集元数据.json")
if os.path.exists(arxiv_meta):
    with open(arxiv_meta, 'r', encoding='utf-8') as f:
        arxiv = json.load(f)
    # Map to B1 format
    for p in arxiv:
        all_papers.append({
            'title': p['title'],
            'year': int(p.get('year', 0) or 0),
            'authors': p.get('authors', ''),
            'keywords': [],  # Will extract from title
            'doi': '',
            'source': 'arXiv'
        })
    print(f"  阿语大采集: {len(arxiv)} 篇")

# Remove duplicates by title
seen_titles = set()
unique = []
for p in all_papers:
    t = p.get('title', '').strip().lower()[:60]
    if t and t not in seen_titles:
        seen_titles.add(t)
        unique.append(p)
all_papers = unique
print(f"  ✅ 去重后总计: {len(all_papers)} 篇文献")

# ====== 2. Extract keywords from titles ======
print("\n📂 术语抽取 (从标题 + 已有术语表)...")

# Build frequency dict from titles
title_words = Counter()
word_in_papers = defaultdict(set)
for i, p in enumerate(all_papers):
    title = p.get('title', '')
    # Tokenize
    words = re.findall(r'[a-zA-Z][a-zA-Z\-\']{2,}', title.lower())
    # Chinese words
    cjk = re.findall(r'[\u4e00-\u9fff]{2,6}', title)
    
    for w in set(words):
        title_words[w] += 1
        word_in_papers[w].add(i)
    for w in set(cjk):
        title_words[w] += 1
        word_in_papers[w].add(i)

# Extract meaningful n-grams
n_grams = Counter()
for p in all_papers:
    title = p.get('title', '')
    words = re.findall(r'[a-zA-Z][a-zA-Z\-\']{2,}', title.lower())
    cjk = re.findall(r'[\u4e00-\u9fff]{2,6}', title)
    
    # Bigrams and trigrams from English
    for n in [2, 3]:
        for i in range(len(words) - n + 1):
            ng = ' '.join(words[i:i+n])
            n_grams[ng] += 1
    
    # Bigrams from Chinese
    for i in range(len(cjk) - 1):
        ng = cjk[i] + cjk[i+1]
        n_grams[ng] += 1

# Score terms: frequency × IDF
total = len(all_papers)
term_scores = {}

for w, freq in title_words.most_common(3000):
    if freq < 3: break
    idf = math.log(total / (len(word_in_papers[w]) + 1))
    term_scores[w] = freq * idf

for ng, freq in n_grams.most_common(3000):
    if freq < 2: break
    term_scores[ng] = freq * math.log(total / (freq + 1))

# Load existing term alignment for expansion
existing_terms = {}
for path in [f"{KG}/术语对齐表_v2.json", f"{KG}/核心术语.json"]:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for d in data if isinstance(data, list) else data.values():
            if isinstance(d, dict) and 'en' in d:
                existing_terms[d['en'].lower()] = d

# Merge: existing terms + new extracted terms
all_terms = {}
for term, score in sorted(term_scores.items(), key=lambda x: -x[1])[:8000]:
    all_terms[term] = {'en': term, 'score': score, 'freq': title_words.get(term, 0)}

# Add existing terms
for k, v in existing_terms.items():
    if k not in all_terms:
        all_terms[k] = v

print(f"  ✅ 核心术语: {len(all_terms)} 条 (目标8000+)")

# ====== 3. Build term alignment (Chinese + Arabic) ======
print("\n📂 构建中阿英术语对齐表...")

# Domain detection
DOMAIN_MAP = {
    '旅游': ['tourism','tourist','travel','hotel','destination','hospitality','visitor','journey','vacation','resort','sightseeing','tour','leisure', '游客', '旅游', '旅行', '酒店', '目的地', '导游', '景区'],
    '文化遗产': ['heritage','conservation','preservation','museum','archaeolog','artifact','antiquity','excavation','monument','tomb','cultural site','遗产', '文物', '考古', '博物', '保护', '遗址', '石窟', '墓葬'],
    '阿拉伯文化': ['arab','islam','muslim','quran','hajj','umrah','mosque','caliphate','bedouin','souk','medina','allah','清真', '阿拉伯', '伊斯兰', '穆斯林', '古兰经'],
    '中阿关系': ['silk road','belt and road','china arab','china middle east','sino arab','一带一路', '丝绸之路', '中阿', '丝路'],
    '数字技术': ['digital','ai','artificial intelligence','machine learning','deep learning','neural','nlp','natural language','computer vision','data mining','recommender','knowledge graph','数据', '智能', '数字', '算法', '模型'],
    '政策法规': ['policy','regulation','governance','strategy','initiative','law','legal','compliance','政策', '法规', '战略', '治理', '合规'],
    '研究方法': ['method','analysis','survey','framework','approach','model','algorithm','technique','methodology','研究', '方法', '分析', '框架'],
}

def detect_domain(en_term):
    et = en_term.lower()
    for domain, kws in DOMAIN_MAP.items():
        for kw in kws:
            if kw in et: return domain
    return '通用'

# Arabic translation dictionary (expanded)
AR_DICT = {
    # Arabic NLP
    'arabic': 'عربي', 'arab': 'عربي', 'arabian': 'عربي',
    'language': 'لغة', 'natural language': 'لغة طبيعية',
    'processing': 'معالجة', 'nlp': 'معالجة اللغة الطبيعية',
    'corpus': 'مدونة', 'dataset': 'مجموعة بيانات',
    'translation': 'ترجمة', 'machine translation': 'ترجمة آلية',
    'sentiment': 'مشاعر', 'sentiment analysis': 'تحليل المشاعر',
    'named entity': 'كيان مسمى', 'named entity recognition': 'التعرف على الكيان المسمى',
    'classification': 'تصنيف', 'text classification': 'تصنيف النص',
    'summarization': 'تلخيص', 'text summarization': 'تلخيص النص',
    'question answering': 'الإجابة على الأسئلة',
    'information retrieval': 'استرجاع المعلومات',
    'morphology': 'صرف', 'morphological': 'صرفي',
    'parsing': 'إعراب', 'dependency parsing': 'إعراب تبعي',
    'word embedding': 'تضمين الكلمات',
    'part of speech': 'نوع الكلمة', 'pos tagging': 'وسم نوع الكلمة',
    'dialect': 'لهجة', 'dialect identification': 'تحديد اللهجة',
    'handwriting': 'كتابة يدوية', 'handwritten': 'مكتوب بخط اليد',
    'ocr': 'التعرف البصري', 'optical character': 'التعرف البصري على الحروف',
    'manuscript': 'مخطوطة', 'historical': 'تاريخي',
    'poetry': 'شعر', 'poem': 'قصيدة',
    'multilingual': 'متعدد اللغات', 'cross lingual': 'عبر اللغات',
    
    # Tourism
    'tourism': 'سياحة', 'tourist': 'سائح', 'travel': 'سفر',
    'hotel': 'فندق', 'destination': 'وجهة', 'hospitality': 'ضيافة',
    'recommender': 'موصي', 'recommendation': 'توصية',
    'smart tourism': 'سياحة ذكية', 'cultural tourism': 'سياحة ثقافية',
    'demand forecasting': 'التنبؤ بالطلب',
    'behavior': 'سلوك', 'tourist behavior': 'سلوك السائح',
    
    # Heritage
    'heritage': 'تراث', 'cultural heritage': 'تراث ثقافي',
    'conservation': 'حفظ', 'preservation': 'محافظة',
    'museum': 'متحف', 'archaeological': 'أثري',
    'artifact': 'قطعة أثرية', 'monument': 'نصب تذكاري',
    'digital heritage': 'تراث رقمي', '3d reconstruction': 'إعادة بناء ثلاثية الأبعاد',
    'site detection': 'كشف المواقع', 'object detection': 'كشف الأشياء',
    
    # China-Arab
    'silk road': 'طريق الحرير', 'belt and road': 'الحزام والطريق',
    'china': 'الصين', 'cooperation': 'تعاون',
    'cultural exchange': 'تبادل ثقافي',
    
    # Islamic
    'islamic': 'إسلامي', 'muslim': 'مسلم', 'quran': 'القرآن',
    'hajj': 'حج', 'umrah': 'عمرة', 'mosque': 'مسجد',
    'hadith': 'حديث', 'islamic finance': 'تمويل إسلامي',
    
    # Tech
    'machine learning': 'تعلم آلي', 'deep learning': 'تعلم عميق',
    'neural network': 'شبكة عصبية', 'artificial intelligence': 'ذكاء اصطناعي',
    'computer vision': 'رؤية حاسوبية', 'data mining': 'تنقيب في البيانات',
    'knowledge graph': 'رسم المعرفة',
    'generative': 'توليدي', 'generation': 'توليد',
    'digital': 'رقمي', 'digital transformation': 'تحول رقمي',
    'model': 'نموذج', 'modeling': 'نمذجة',
    'analysis': 'تحليل', 'framework': 'إطار',
    'prediction': 'تنبؤ', 'forecasting': 'التنبؤ',
}

def translate_ar(en_term):
    et = en_term.lower()
    if et in AR_DICT:
        return AR_DICT[et]
    # Try partial match (longest first)
    for k, v in sorted(AR_DICT.items(), key=lambda x: -len(x[0])):
        if k in et:
            return v
    return ''

def translate_cn(en_term):
    """Generate Chinese translation from term components"""
    et = en_term.lower()
    cn_map = {}
    # Single words
    cn_map.update({
        'tourism':'旅游','tourist':'游客','travel':'旅行','hotel':'酒店',
        'destination':'目的地','hospitality':'款待','heritage':'遗产',
        'cultural':'文化','culture':'文化','conservation':'保护',
        'preservation':'保存','museum':'博物馆','archaeolog':'考古',
        'arabic':'阿拉伯语','arab':'阿拉伯','islam':'伊斯兰','muslim':'穆斯林',
        'silk':'丝绸','china':'中国','language':'语言','natural':'自然',
        'processing':'处理','translation':'翻译','sentiment':'情感',
        'classification':'分类','recognition':'识别','extraction':'提取',
        'generation':'生成','generative':'生成式','summarization':'摘要',
        'digital':'数字','smart':'智慧','intelligent':'智能',
        'learning':'学习','neural':'神经','network':'网络','model':'模型',
        'analysis':'分析','detection':'检测','recommender':'推荐',
        'prediction':'预测','forecasting':'预测','evaluation':'评估',
        'review':'评论','behavior':'行为','image':'图像',
        'text':'文本','data':'数据','mining':'挖掘',
        'machine':'机器','deep':'深度','artificial':'人工',
        'vision':'视觉','knowledge':'知识','graph':'图谱',
        'management':'管理','development':'发展','research':'研究',
        'dialect':'方言','historical':'历史','manuscript':'手稿',
        'poetry':'诗歌','cross':'跨','lingual':'语言',
        'multilingual':'多语','low resource':'低资源',
        'endangered':'濒危','code switching':'语码转换',
        'document':'文档','information':'信息','retrieval':'检索',
        'morphology':'形态学','parsing':'句法分析',
        'embedding':'嵌入','corpus':'语料库','question':'问题',
        'answering':'回答','handwritten':'手写','optical':'光学',
        'character':'字符','reconstruction':'重建',
        'computation':'计算','computational':'计算',
    })
    
    if et in cn_map:
        return cn_map[et]
    for k, v in sorted(cn_map.items(), key=lambda x: -len(x[0])):
        if k in et:
            return v
    return ''

# Build alignment
alignment = []
for term, data in sorted(all_terms.items(), key=lambda x: -x[1].get('score', 0)):
    en = term
    cn = data.get('cn', '') or translate_cn(en)
    ar = data.get('ar', '') or translate_ar(en)
    domain = detect_domain(en)
    
    alignment.append({
        'en': en,
        'cn': cn,
        'ar': ar,
        'domain': domain if domain != '通用' or cn else '通用',
        'freq': data.get('freq', 0),
        'source': '文献标题',
    })

# Sort: those with translations first
alignment.sort(key=lambda x: (-bool(x['cn']), -bool(x['ar']), -x['freq']))
print(f"  ✅ 术语对齐表: {len(alignment)} 条 (目标8000+)")
print(f"     有中文: {sum(1 for a in alignment if a['cn'])} 条")
print(f"     有阿语: {sum(1 for a in alignment if a['ar'])} 条")

# ====== 4. Entity types & instances ======
print("\n📂 构建实体实例 (8000+)...")

# Extract entities from papers and terms
entities = []
entity_id = 0

# Papers as entities
for i, p in enumerate(all_papers[:8000]):
    entity_id += 1
    entities.append({
        'id': entity_id,
        'type': 'Paper',
        'label': p.get('title', '')[:80],
        'year': p.get('year', ''),
        'authors': p.get('authors', '')[:100],
    })

# Top terms as Topic entities
for a in alignment[:2000]:
    if a['en'] and len(a['en']) > 2:
        entity_id += 1
        entities.append({
            'id': entity_id,
            'type': 'Topic',
            'label': a['en'],
            'domain': a['domain'],
        })

print(f"  ✅ 实体实例: {len(entities)} 个 (目标8000+)")

# ====== 5. Build relationships ======
print("\n📂 构建关系 (Paper→Topic)...")

rels = []
for i, p in enumerate(all_papers[:5000]):
    title = p.get('title', '').lower()
    for a in alignment[:500]:
        if len(a['en']) > 3 and a['en'].lower() in title:
            # Find entity id
            paper_entity = next((e for e in entities if e['type']=='Paper' and e.get('label','')[:30] in p.get('title','')[:30]), None)
            topic_entity = next((e for e in entities if e['type']=='Topic' and e['label']==a['en']), None)
            if paper_entity and topic_entity:
                rels.append({
                    'source': paper_entity['id'],
                    'target': topic_entity['id'],
                    'type': 'studies',
                    'weight': 1
                })
                break  # One relation per paper to avoid explosion

print(f"  ✅ 关系: {len(rels)} 条")

# ====== 6. Save ======
print("\n📂 保存结果...")

# Save term alignment
output = {'terms': alignment, 'entities': entities, 'relations': rels}
with open(os.path.join(KG, "知识图谱2.0.json"), 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

# Save alignment table separately
with open(os.path.join(KG, "术语对齐表_v3.json"), 'w', encoding='utf-8') as f:
    json.dump(alignment, f, ensure_ascii=False, indent=2)

# Build NetworkX graph
import networkx as nx
G = nx.Graph()
for e in entities:
    G.add_node(e['id'], type=e['type'], label=e.get('label',''), domain=e.get('domain',''))
for r in rels:
    G.add_edge(r['source'], r['target'], type=r['type'], weight=r['weight'])

# Clean None values
for n, data in G.nodes(data=True):
    for k, v in list(data.items()):
        if v is None: data[k] = ''
for u, v, data in G.edges(data=True):
    for k, v in list(data.items()):
        if v is None: data[k] = ''

nx.write_gexf(G, os.path.join(KG, "知识图谱2.0.gexf"))
nx.write_graphml(G, os.path.join(KG, "知识图谱2.0.graphml"))

# Domain distribution
domain_count = Counter(a['domain'] for a in alignment)
print(f"\n{'='*60}")
print(f"  ✅ 中阿文旅知识图谱2.0 构建完成!")
print(f"  📊 术语对齐表: {len(alignment)} 条")
print(f"  🟢 实体实例: {len(entities)} 个")
print(f"  🔗 关系: {len(rels)} 条")
print(f"  🕸️ 图谱节点: {G.number_of_nodes()}")
print(f"")  
print(f"  术语领域分布:")
for d, c in sorted(domain_count.items(), key=lambda x:-x[1])[:10]:
    print(f"    {d}: {c}")
print(f"{'='*60}")
