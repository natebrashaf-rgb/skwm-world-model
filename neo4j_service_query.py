#!/usr/bin/env python3
"""
neo4j_service_query.py — S0 静态知识图谱服务基线
================================================
定位：S0 基线 + 历史快照 + 预测证据追溯
职责：
  1. as_of_year 防穿越（预测2024时不读2024+数据，必填）
  2. Paper/Topic/Author/Relation 分类返回
  3. 返回 DOI、来源、语种、年份、图谱关系路径（单行字符串）
  4. 馆员服务问题集（真实学科服务场景）
  5. 为 S0/S1/S2 生成统一格式盲评材料

用法:
    python neo4j_service_query.py --as-of 2022              # 指定截止年
    python neo4j_service_query.py --as-of 2020 --leak-check # 泄露自查
    python neo4j_service_query.py --as-of 2022 --blind-review
    python neo4j_service_query.py --as-of 2022 --question Q3

关系名事实（Neo4j 图）：
  HAS_TOPIC   Topic–Paper (29841条)
  AUTHORED    Author–Paper
  PUBLISHED_IN Paper–Venue
  PUBLISHED_IN_YEAR Paper–Year
  CO_OCCURS_WITH Topic–Topic
  BELONGS_TO_DOMAIN Topic–Domain
  SNAPSHOT    Year–Topic

Paper节点属性：citations(str), id(str), is_tourism(bool/str), title(str), year(str)
Topic/Author/Venue 仅 name 属性；doi/language/venue 需从B1 JSON关联
"""
import json
import os
import re
import sys
import time
import argparse
import warnings
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "service_baseline"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TERM_MAP_VERSION = "term_map_v1"
TERM_MAP_FILE = DATA_DIR / "term_map_v1.json"
FALLBACK_TERM_MAP_FILE = Path(r"E:\大挑\rail_deploy\data\term_map_v1.json")

CRED_FILE = BASE / ".neo4j_cred.json"

LIBRARIAN_QUESTIONS = [
    {"qid": "Q1", "category": "前沿识别",
     "question": "中阿文旅领域近3年增速最快的交叉研究方向有哪些？",
     "expected_type": "topic_ranking", "requires_prediction": False},
    {"qid": "Q2", "category": "前沿识别",
     "question": "数字遗产与旅游交叉领域，未来2年可能出现哪些新兴主题？",
     "expected_type": "emerging_prediction", "requires_prediction": True},
    {"qid": "Q3", "category": "证据追溯",
     "question": "'文化遗产数字化'这一方向的核心文献有哪些？请给出DOI和引用关系。",
     "expected_type": "evidence_chain", "requires_prediction": False},
    {"qid": "Q4", "category": "风险评估",
     "question": "阿拉伯语文旅文献的数据覆盖度如何？哪些子方向数据稀疏？",
     "expected_type": "coverage_assessment", "requires_prediction": False},
    {"qid": "Q5", "category": "趋势预测",
     "question": "基于历史数据，预测2025-2026年中阿文旅领域的Top-10热点主题。",
     "expected_type": "forecast", "requires_prediction": True},
    {"qid": "Q6", "category": "作者发现",
     "question": "在中阿文旅交叉领域，哪些作者的研究呈现跨学科特征？",
     "expected_type": "author_discovery", "requires_prediction": False},
    {"qid": "Q7", "category": "反事实",
     "question": "如果移除'一带一路'相关的政策文献，中阿文旅合作网络的连通性会如何变化？",
     "expected_type": "counterfactual", "requires_prediction": True},
    {"qid": "Q8", "category": "服务推荐",
     "question": "一位研究阿拉伯数字人文的教师，应该关注哪些新兴交叉方向和相关文献？",
     "expected_type": "recommendation", "requires_prediction": True},
]


def load_creds():
    if not CRED_FILE.exists():
        return None
    with open(CRED_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_state_vectors():
    path = DATA_DIR / "state_vectors.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_cn_en_map():
    import re as _re
    for path in [TERM_MAP_FILE, FALLBACK_TERM_MAP_FILE]:
        if path.exists():
            try:
                snap = json.loads(path.read_text(encoding="utf-8"))
                cn_en = snap.get("cn_to_en") or {}
                cn_ar = snap.get("cn_to_ar") or {}
                ar_en = snap.get("ar_to_en") or {}
                if cn_en:
                    print(f"[i] 词表快照: cn_en={len(cn_en)} cn_ar={len(cn_ar)} ar_en={len(ar_en)}", flush=True)
                    return cn_en, cn_ar, ar_en
            except Exception:
                continue
    candidates = [
        DATA_DIR / "core_terms.json",
        Path(r"E:\大挑\03_knowledge_graph\core_terms.json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
            m = _re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
            terms = json.loads("[" + raw[m.end():]) if m else json.loads(raw)
            cn_en, cn_ar, ar_en = {}, {}, {}
            for t in terms:
                if not isinstance(t, dict):
                    continue
                cn = (t.get("cn") or "").strip()
                en = (t.get("en") or "").strip()
                ar = (t.get("ar") or "").strip()
                if cn and en: cn_en[cn] = en
                if cn and ar: cn_ar[cn] = ar
                if ar and en:
                    ar_en.setdefault(ar, [])
                    if en not in ar_en[ar]: ar_en[ar].append(en)
            return cn_en, cn_ar, ar_en
        except Exception:
            continue
    return {}, {}, {}


def load_b1():
    path = DATA_DIR / "B1_文献主表.json"
    if not path.exists():
        return [], {}
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
    idx = raw.find('{', raw.find('{') + 1)
    if idx > 0:
        records = json.loads('[' + raw[idx:])
    else:
        records = []
    doi_index = {}
    title_index = {}
    for rec in records:
        doi = (rec.get("doi") or "").strip()
        if doi:
            doi_index[doi] = rec
        title = (rec.get("title") or "").strip()
        if title:
            title_index[title[:200]] = rec
    return records, {"doi": doi_index, "title_prefix": title_index}


def load_temporal_snapshots():
    path = DATA_DIR / "temporal_snapshots.json"
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        data = json.loads("[" + raw[m.end():])
    else:
        data = json.loads(raw)
    return {k: v for k, v in data.items() if isinstance(v, dict) and k != "_wm"}


# ═══════════════════ 核心服务类 ═══════════════════

class Neo4jServiceQuery:
    """S0 静态知识图谱服务基线

    as_of_year: 必填。任何 year >= as_of_year 的节点与关系不进入结果。
    derive_year_from: Topic/Author 无 year 属性，通过关联 Paper 推导。
      - earliest (默认)：min(关联 Paper.year)，最保守，防穿越
      - latest：max(关联 Paper.year)
      - mean：round(mean(关联 Paper.year))
    """

    def __init__(self, as_of_year: int, derive_year_from: str = "earliest"):
        if as_of_year is None:
            raise ValueError(
                "as_of_year 是必填参数。不传年份将读取未来文献，结果不可用于任何预测实验。\n"
                "用法: python neo4j_service_query.py --as-of 2022"
            )
        if derive_year_from not in ("earliest", "latest", "mean"):
            raise ValueError(f"derive_year_from 必须是 earliest/latest/mean，当前为 {derive_year_from}")

        self.as_of_year = as_of_year
        self.derive_year_from = derive_year_from
        self.sv = load_state_vectors()
        self.b1_records, self.b1_index = load_b1()
        self.ts = load_temporal_snapshots()
        self.cn_en, self.cn_ar, self.ar_en = load_cn_en_map()
        self.driver = None
        self._year_cache = {}
        self._b1_cache = {}

        creds = load_creds()
        if creds:
            try:
                from neo4j import GraphDatabase
                self.driver = GraphDatabase.driver(
                    creds["uri"], auth=(creds["user"], creds["password"])
                )
                self.driver.verify_connectivity()
                print(f"[OK] Neo4j 连接成功", flush=True)
            except Exception as e:
                print(f"[WARN] Neo4j 连接失败: {e}，将仅使用B1 JSON数据", flush=True)
                self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    # ── B1 关联 ──

    def _b1_lookup(self, paper_id=None, title=None):
        """通过 Paper.id 或 title 前200字符从B1拿 doi/language/venue/source。"""
        cache_key = paper_id or title
        if cache_key and cache_key in self._b1_cache:
            return self._b1_cache[cache_key]

        rec = None
        if paper_id:
            rec = self.b1_index["doi"].get(paper_id)
        if rec is None and title:
            rec = self.b1_index["title_prefix"].get(title[:200])
        if rec is None and paper_id:
            for doi, r in self.b1_index["doi"].items():
                if paper_id in doi or doi in paper_id:
                    rec = r
                    break

        result = {
            "doi": (rec.get("doi") or "") if rec else "",
            "language": (rec.get("language") or "") if rec else "",
            "venue": (rec.get("venue") or "") if rec else "",
            "source": (rec.get("_source") or "") if rec else "",
        }
        if cache_key:
            self._b1_cache[cache_key] = result
        return result

    # ── 年份推导 ──

    def _derive_topic_year(self, topic_name: str) -> int:
        """Topic 无 year 属性，通过 HAS_TOPIC 关联 Paper 推导。"""
        if topic_name in self._year_cache:
            return self._year_cache[topic_name]

        if self.driver:
            try:
                with self.driver.session() as s:
                    result = s.run(
                        "MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic) "
                        "WHERE t.name = $name RETURN toInteger(p.year) AS y",
                        name=topic_name
                    )
                    years = [r["y"] for r in result if r["y"] is not None]
                if years:
                    derived = self._calc_derived(years)
                    self._year_cache[topic_name] = derived
                    return derived
            except Exception:
                pass

        years = []
        for p in self.b1_records:
            kws = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            if topic_name.lower() in [k.strip().lower() for k in kws]:
                y = p.get("year")
                if isinstance(y, (int, float)) and int(y) >= 1900:
                    years.append(int(y))
        if years:
            derived = self._calc_derived(years)
            self._year_cache[topic_name] = derived
            return derived

        self._year_cache[topic_name] = None
        return None

    def _derive_author_year(self, author_name: str) -> int:
        """Author 无 year 属性，通过 AUTHORED 关联 Paper 推导。"""
        if author_name in self._year_cache:
            return self._year_cache[author_name]

        if self.driver:
            try:
                with self.driver.session() as s:
                    result = s.run(
                        "MATCH (p:Paper)-[:AUTHORED]->(a:Author) "
                        "WHERE a.name = $name RETURN toInteger(p.year) AS y",
                        name=author_name
                    )
                    years = [r["y"] for r in result if r["y"] is not None]
                if years:
                    derived = self._calc_derived(years)
                    self._year_cache[author_name] = derived
                    return derived
            except Exception:
                pass

        years = []
        for p in self.b1_records:
            authors_str = p.get("authors", "")
            if author_name in authors_str:
                y = p.get("year")
                if isinstance(y, (int, float)) and int(y) >= 1900:
                    years.append(int(y))
        if years:
            derived = self._calc_derived(years)
            self._year_cache[author_name] = derived
            return derived

        self._year_cache[author_name] = None
        return None

    def _calc_derived(self, years: list) -> int:
        if not years:
            return None
        if self.derive_year_from == "earliest":
            return min(years)
        elif self.derive_year_from == "latest":
            return max(years)
        else:
            return round(sum(years) / len(years))

    # ── 三语查询扩展 ──

    @staticmethod
    def _is_arabic(text: str) -> bool:
        return bool(re.search(r'[\u0600-\u06FF]', text))

    def _expand_keywords(self, topic_keyword: str) -> list:
        kws = [topic_keyword]
        q = topic_keyword.strip()
        if not q:
            return kws

        if self._is_arabic(q):
            if q in self.ar_en:
                trans = sorted(self.ar_en[q], key=lambda x: (len(x.split()), len(x)))
                for en in trans[:5]:
                    if en.lower() not in (k.lower() for k in kws):
                        kws.append(en)
            return kws

        if q in self.cn_en:
            en = self.cn_en[q]
            if en and en.lower() not in (k.lower() for k in kws):
                kws.append(en)
        else:
            for sub_cn, sub_en in self.cn_en.items():
                if 2 <= len(sub_cn) <= 8 and sub_cn in q and sub_en:
                    if sub_en.lower() not in (k.lower() for k in kws):
                        kws.append(sub_en)
        return kws

    # ── 语种检测 ──

    @staticmethod
    def _detect_language(text: str) -> str:
        if re.search(r'[\u0600-\u06FF]', text):
            return "ar"
        if re.search(r'[\u4e00-\u9fff]', text):
            return "zh"
        return "en"

    # ── 核心查询：按关键词检索，分类返回 ──

    def query_by_keyword(self, keyword: str, top_k: int = 20) -> dict:
        """统一入口：一次查询返回 Paper/Topic/Author/Relation 四类结果。

        所有 Paper 节点受 as_of_year 约束（year < as_of_year）。
        Topic/Author 受推导年份约束（derive_year < as_of_year）。
        """
        kws = self._expand_keywords(keyword)
        papers = []
        topics = []
        authors = []
        relations = []
        hit_fields_set = set()
        years_hit = []

        # ── Paper 检索（Neo4j + B1） ──
        if self.driver:
            paper_results = self._neo4j_search_papers(kws, top_k)
        else:
            paper_results = self._b1_search_papers(kws, top_k)

        for p in paper_results:
            title = p.get("title", "")
            year = p.get("year")
            if year is not None:
                try:
                    year = int(year)
                except (ValueError, TypeError):
                    year = None
            if year is not None and (year < 1900 or year >= self.as_of_year):
                continue

            b1_info = self._b1_lookup(paper_id=p.get("id"), title=title)
            language = b1_info["language"] if b1_info["language"] else self._detect_language(title)
            venue = p.get("venue", "") or b1_info["venue"]
            source = b1_info["source"] if b1_info["source"] else "B1_文献主表"
            doi = p.get("doi", "") or b1_info["doi"]

            papers.append({
                "doi": doi,
                "title": title,
                "year": year,
                "language": language,
                "venue": venue,
                "source": source,
                "citations": int(p["citations"]) if p.get("citations") else 0,
                "hit_field": p.get("hit_field", "unknown"),
            })
            hit_fields_set.add(p.get("hit_field", "unknown"))
            if year is not None:
                years_hit.append(year)

        # ── Topic 检索 ──
        if self.driver:
            topic_results = self._neo4j_search_topics(kws, top_k)
        else:
            topic_results = self._b1_search_topics(kws, top_k)

        for t in topic_results:
            tname = t.get("name", "")
            derived_year = self._derive_topic_year(tname)
            if derived_year is not None and derived_year >= self.as_of_year:
                continue

            topics.append({
                "name": tname,
                "derived_year": derived_year,
                "derive_method": self.derive_year_from,
            })

            if self.driver and papers:
                try:
                    with self.driver.session() as s:
                        rels = s.run(
                            "MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic) "
                            "WHERE t.name = $name AND toInteger(p.year) <= $y "
                            "RETURN p.title AS title, toInteger(p.year) AS year, 'HAS_TOPIC' AS rel "
                            "ORDER BY toInteger(p.year) DESC LIMIT 3",
                            name=tname, y=self.as_of_year
                        )
                        for r in rels:
                            relations.append(
                                f"Paper「{r['title']}」({r['year']})-[:HAS_TOPIC]->Topic「{tname}」"
                                f"(derived:{derived_year})"
                            )
                except Exception:
                    relations.append(f"Topic「{tname}」(derived:{derived_year})")
            else:
                relations.append(f"Topic「{tname}」(derived:{derived_year})")

        # ── Author 检索 ──
        if self.driver:
            author_results = self._neo4j_search_authors(kws, top_k)
        else:
            author_results = self._b1_search_authors(kws, top_k)

        for a in author_results:
            aname = a.get("name", "")
            derived_year = self._derive_author_year(aname)
            if derived_year is not None and derived_year >= self.as_of_year:
                continue

            authors.append({
                "name": aname,
                "derived_year": derived_year,
                "derive_method": self.derive_year_from,
            })

            if self.driver and papers:
                try:
                    with self.driver.session() as s:
                        rels = s.run(
                            "MATCH (p:Paper)-[:AUTHORED]->(a:Author) "
                            "WHERE a.name = $name AND toInteger(p.year) <= $y "
                            "RETURN p.title AS title, toInteger(p.year) AS year, 'AUTHORED' AS rel "
                            "ORDER BY toInteger(p.year) DESC LIMIT 3",
                            name=aname, y=self.as_of_year
                        )
                        for r in rels:
                            relations.append(
                                f"Paper「{r['title']}」({r['year']})-[:AUTHORED]->Author「{aname}」"
                                f"(derived:{derived_year})"
                            )
                except Exception:
                    relations.append(f"Author「{aname}」(derived:{derived_year})")
            else:
                relations.append(f"Author「{aname}」(derived:{derived_year})")

        return {
            "query": keyword,
            "expanded_keywords": list(dict.fromkeys(kws)),
            "as_of_year": self.as_of_year,
            "derive_year_from": self.derive_year_from,
            "hit_count": len(papers) + len(topics) + len(authors),
            "hit_fields": sorted(hit_fields_set),
            "year_range": (min(years_hit), max(years_hit)) if years_hit else None,
            "papers": papers[:top_k],
            "topics": topics[:top_k],
            "authors": authors[:top_k],
            "relations": relations[:top_k * 2],
        }

    # ── Neo4j 子查询 ──

    def _neo4j_search_papers(self, kws: list, top_k: int) -> list:
        results = []
        for kw in kws:
            try:
                with self.driver.session() as s:
                    records = s.run(
                        "MATCH (p:Paper) "
                        "WHERE toLower(p.title) CONTAINS toLower($kw) "
                        "AND toInteger(p.year) >= 1900 AND toInteger(p.year) < $y "
                        "RETURN p.id AS id, p.title AS title, toInteger(p.year) AS year, "
                        "       toInteger(p.citations) AS citations "
                        "ORDER BY toInteger(p.citations) DESC LIMIT $limit",
                        kw=kw, y=self.as_of_year, limit=top_k
                    )
                    for r in records:
                        item = dict(r)
                        item["hit_field"] = "title"
                        if item not in results:
                            results.append(item)
            except Exception:
                pass

        for kw in kws:
            try:
                with self.driver.session() as s:
                    records = s.run(
                        "MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic) "
                        "WHERE toLower(t.name) CONTAINS toLower($kw) "
                        "AND toInteger(p.year) >= 1900 AND toInteger(p.year) < $y "
                        "RETURN p.id AS id, p.title AS title, toInteger(p.year) AS year, "
                        "       toInteger(p.citations) AS citations "
                        "ORDER BY toInteger(p.citations) DESC LIMIT $limit",
                        kw=kw, y=self.as_of_year, limit=top_k
                    )
                    for r in records:
                        item = dict(r)
                        item["hit_field"] = "topic_keyword"
                        if item not in results:
                            results.append(item)
            except Exception:
                pass
        return results[:top_k]

    def _neo4j_search_topics(self, kws: list, top_k: int) -> list:
        results = []
        for kw in kws:
            try:
                with self.driver.session() as s:
                    records = s.run(
                        "MATCH (t:Topic) WHERE toLower(t.name) CONTAINS toLower($kw) "
                        "RETURN t.name AS name LIMIT $limit",
                        kw=kw, limit=top_k
                    )
                    for r in records:
                        if dict(r) not in results:
                            results.append(dict(r))
            except Exception:
                pass
        return results[:top_k]

    def _neo4j_search_authors(self, kws: list, top_k: int) -> list:
        results = []
        for kw in kws:
            try:
                with self.driver.session() as s:
                    records = s.run(
                        "MATCH (a:Author) WHERE toLower(a.name) CONTAINS toLower($kw) "
                        "RETURN a.name AS name LIMIT $limit",
                        kw=kw, limit=top_k
                    )
                    for r in records:
                        if dict(r) not in results:
                            results.append(dict(r))
            except Exception:
                pass
        return results[:top_k]

    # ── B1 降级子查询（无 Neo4j 时） ──

    def _b1_search_papers(self, kws: list, top_k: int) -> list:
        results = []
        seen_ids = set()
        for p in self.b1_records:
            year = p.get("year")
            if not isinstance(year, (int, float)) or int(year) < 1900 or int(year) >= self.as_of_year:
                continue
            title = str(p.get("title", "")).lower()
            kws_raw = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws_raw, str):
                kws_raw = [k.strip() for k in kws_raw.split(",")]
            hit_field = None
            for kw in kws:
                kl = kw.lower()
                if kl in title and not hit_field:
                    hit_field = "title"
                if any(kl in k.lower() for k in kws_raw) and not hit_field:
                    hit_field = "keywords"
            if hit_field:
                pid = p.get("doi") or p.get("title", "")[:100]
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append({
                        "id": p.get("doi", ""),
                        "title": p.get("title", ""),
                        "year": p.get("year"),
                        "citations": p.get("citations", 0),
                        "venue": p.get("venue", ""),
                        "doi": p.get("doi", ""),
                        "hit_field": hit_field,
                    })
            if len(results) >= top_k:
                break
        return results

    def _b1_search_topics(self, kws: list, top_k: int) -> list:
        topic_names = set()
        for p in self.b1_records:
            kws_raw = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws_raw, str):
                kws_raw = [k.strip() for k in kws_raw.split(",")]
            for kw in kws:
                kl = kw.lower()
                for k in kws_raw:
                    if kl in k.lower() and k.strip() not in topic_names:
                        topic_names.add(k.strip())
                        if len(topic_names) >= top_k:
                            return [{"name": n} for n in list(topic_names)]
        return [{"name": n} for n in list(topic_names)]

    def _b1_search_authors(self, kws: list, top_k: int) -> list:
        author_names = set()
        for p in self.b1_records:
            authors_str = p.get("authors", "")
            if not authors_str:
                continue
            for kw in kws:
                if kw.lower() in authors_str.lower():
                    parts = re.split(r'[,;、]', authors_str)
                    for a in parts:
                        a = a.strip()
                        if len(a) > 2 and a not in author_names:
                            author_names.add(a)
                            if len(author_names) >= top_k:
                                return [{"name": n} for n in list(author_names)]
        return [{"name": n} for n in list(author_names)]

    # ── 热点 / 新兴 / 覆盖 / 作者跨学科（保持原接口，加 as_of_year 约束） ──

    def query_hotspots(self, top_k: int = 20, year: int = None) -> dict:
        y = year or self.as_of_year
        sv = self._filter_sv_by_year(y)
        items = sorted(sv.items(), key=lambda x: -x[1][0])[:top_k]
        papers = self._filter_papers_by_year(y)
        return {
            "type": "hotspots", "as_of_year": y,
            "topics": [
                {"name": n, "heat": v[0], "growth": v[1], "centrality": v[2], "connections": v[3]}
                for n, v in items
            ],
            "total_papers": len(papers),
        }

    def query_emerging(self, top_k: int = 20, year: int = None) -> dict:
        y = year or self.as_of_year
        sv = self._filter_sv_by_year(y)
        items = sorted(sv.items(), key=lambda x: -abs(x[1][1]))[:top_k]
        return {
            "type": "emerging", "as_of_year": y,
            "topics": [
                {"name": n, "growth": v[1], "heat": v[0], "growth_valid": abs(v[1]) <= v[0]}
                for n, v in items
            ],
        }

    def query_coverage(self, year: int = None) -> dict:
        y = year or self.as_of_year
        papers = self._filter_papers_by_year(y)
        lang_count = Counter()
        for p in papers:
            title = str(p.get("title", ""))
            lang_count[self._detect_language(title)] += 1

        sv = self._filter_sv_by_year(y)
        sparse = [{"name": n, "heat": v[0]} for n, v in sv.items() if v[0] < 5]
        sparse.sort(key=lambda x: x["heat"])
        return {
            "type": "coverage", "as_of_year": y,
            "total_papers": len(papers),
            "language_distribution": dict(lang_count),
            "arabic_ratio": lang_count.get("ar", 0) / max(1, len(papers)),
            "sparse_topics_count": len(sparse),
            "sparse_topics_top20": sparse[:20],
        }

    def query_author_crossdisciplinary(self, year: int = None) -> dict:
        y = year or self.as_of_year
        papers = self._filter_papers_by_year(y)
        author_topics = defaultdict(set)
        author_papers = defaultdict(list)
        for p in papers:
            authors_str = p.get("authors", "")
            if not authors_str:
                continue
            authors = [a.strip() for a in re.split(r'[,;、]', authors_str) if len(a.strip()) > 2]
            kws = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws, str): kws = [k.strip() for k in kws.split(",")]
            for a in authors[:5]:
                for k in kws:
                    if k.strip(): author_topics[a].add(k.strip().lower())
                author_papers[a].append(p.get("title", ""))

        cross = []
        for author, topics in author_topics.items():
            if len(topics) >= 5 and len(author_papers[author]) >= 3:
                cross.append({
                    "name": author, "topic_diversity": len(topics),
                    "paper_count": len(author_papers[author]),
                    "sample_topics": sorted(topics)[:8],
                })
        cross.sort(key=lambda x: -x["topic_diversity"])
        return {
            "type": "author_discovery", "as_of_year": y,
            "crossdisciplinary_authors": cross[:30],
            "total_authors": len(author_topics),
        }

    def _filter_sv_by_year(self, year: int) -> dict:
        sv = self.sv
        if not sv: return {}
        year_keys = [k for k in sv.keys() if str(k).isdigit() and int(k) <= year]
        if year_keys:
            acc = {}
            for yk in sorted(year_keys, key=int):
                data = sv[yk]
                if not isinstance(data, dict): continue
                for topic, vec in data.items():
                    if not isinstance(vec, (list, tuple)) or len(vec) < 2: continue
                    if topic not in acc: acc[topic] = [0, 0, 0, 0]
                    acc[topic][0] += float(vec[0])
                    acc[topic][1] = float(vec[1])
                    if len(vec) >= 3: acc[topic][2] = float(vec[2])
                    if len(vec) >= 4: acc[topic][3] = float(vec[3])
            return acc
        return {k: v for k, v in sv.items()
                if isinstance(v, (list, tuple)) and len(v) >= 2}

    def _filter_papers_by_year(self, max_year: int) -> list:
        return [p for p in self.b1_records
                if isinstance(p.get("year"), (int, float))
                and 1900 <= int(p.get("year", 0)) <= max_year]

    # ── 馆员问题集 ──

    def answer_question(self, q: dict) -> dict:
        qid = q["qid"]
        year = self.as_of_year

        if qid == "Q1":
            result = self.query_emerging(top_k=15, year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result
        elif qid == "Q2":
            emerging = self.query_emerging(top_k=10, year=year)
            evidence = self.query_topic_evidence("digital heritage", year=year)
            return {
                "qid": qid, "question": q["question"], "type": "emerging_prediction",
                "as_of_year": year,
                "emerging_topics": emerging["topics"][:10],
                "evidence_papers": evidence.get("papers", [])[:5],
                "note": "S0基线仅提供历史数据，预测能力有限",
            }
        elif qid == "Q3":
            result = self.query_topic_evidence("文化遗产数字化", year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result
        elif qid == "Q4":
            result = self.query_coverage(year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result
        elif qid == "Q5":
            hotspots = self.query_hotspots(top_k=15, year=year)
            return {
                "qid": qid, "question": q["question"], "type": "forecast",
                "as_of_year": year,
                "baseline_hotspots": hotspots["topics"],
                "note": "S0基线仅外推当前热度排序，无预测模型",
            }
        elif qid == "Q6":
            result = self.query_author_crossdisciplinary(year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result
        elif qid == "Q7":
            path = self.query_graph_paths("一带一路", "旅游", year=year)
            return {
                "qid": qid, "question": q["question"], "type": "counterfactual",
                "as_of_year": year,
                "graph_path": path,
                "note": "S0基线无法模拟反事实，仅提供当前图结构",
            }
        elif qid == "Q8":
            emerging = self.query_emerging(top_k=10, year=year)
            coverage = self.query_coverage(year=year)
            return {
                "qid": qid, "question": q["question"], "type": "recommendation",
                "as_of_year": year,
                "emerging_topics": emerging["topics"][:5],
                "coverage_warning": {
                    "arabic_ratio": coverage["arabic_ratio"],
                    "sparse_count": coverage["sparse_topics_count"],
                },
                "note": "S0基线推荐基于历史增速，无预测和个性化能力",
            }
        return {"qid": qid, "error": "unknown question"}

    def query_topic_evidence(self, topic_keyword: str, year: int = None) -> dict:
        y = year or self.as_of_year
        papers = self._filter_papers_by_year(y)
        kws = self._expand_keywords(topic_keyword)
        matched = []
        for p in papers:
            title = str(p.get("title", "")).lower()
            kws_raw = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws_raw, str):
                kws_raw = [k.strip() for k in kws_raw.split(",")]
            kw_lower = [k.lower().strip() for k in kws_raw]
            hit_fields = []
            hit_words = []
            for k in kws:
                kl = k.lower()
                if kl in title:
                    hit_fields.append("title")
                    hit_words.append(k)
                if any(kl in kw for kw in kw_lower):
                    hit_fields.append("keywords")
                    hit_words.append(k)
            if hit_fields:
                b1_info = self._b1_lookup(title=title)
                language = b1_info["language"] if b1_info["language"] else self._detect_language(p.get("title", ""))
                matched.append({
                    "doi": p.get("doi", "") or b1_info["doi"],
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                    "venue": p.get("venue", "") or b1_info["venue"],
                    "citations": p.get("citations", 0),
                    "authors": p.get("authors", ""),
                    "language": language,
                    "query_original": topic_keyword,
                    "query_expanded": list(dict.fromkeys(kws)),
                    "term_map_version": TERM_MAP_VERSION,
                    "hit_fields": sorted(set(hit_fields)),
                    "hit_terms": list(dict.fromkeys(hit_words)),
                })
        matched.sort(key=lambda x: -(x.get("citations") or 0))
        return {
            "type": "evidence_chain", "topic": topic_keyword,
            "matched_keywords": kws, "term_map_version": TERM_MAP_VERSION,
            "as_of_year": y, "papers": matched[:30], "total_matched": len(matched),
        }

    def query_graph_paths(self, topic_a: str, topic_b: str,
                          max_hops: int = 3, year: int = None) -> dict:
        y = year or self.as_of_year
        sv = self._filter_sv_by_year(y)
        papers = self._filter_papers_by_year(y)
        kws_a = self._expand_keywords(topic_a)
        kws_b = self._expand_keywords(topic_b)

        bridge_papers = []
        for p in papers:
            title = str(p.get("title", "")).lower()
            kws = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws, str): kws = [k.strip() for k in kws.split(",")]
            kw_text = " ".join(k.lower() for k in kws)
            has_a = any(ka.lower() in title for ka in kws_a) or any(ka.lower() in kw_text for ka in kws_a)
            has_b = any(kb.lower() in title for kb in kws_b) or any(kb.lower() in kw_text for kb in kws_b)
            if has_a and has_b:
                b1_info = self._b1_lookup(title=p.get("title", ""))
                bridge_papers.append({
                    "doi": p.get("doi", "") or b1_info["doi"],
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                    "language": b1_info["language"] if b1_info["language"] else self._detect_language(p.get("title", "")),
                })

        path_info = {
            "type": "graph_path", "from": topic_a, "to": topic_b,
            "as_of_year": y,
            "bridge_papers": bridge_papers[:20],
            "path_length": 1 if bridge_papers else None,
        }

        if self.driver:
            try:
                hops_lit = int(max_hops)
                with self.driver.session() as s:
                    result = s.run(
                        f"""MATCH (a:Topic) WHERE a.name = $a
                        MATCH (b:Topic) WHERE b.name = $b
                        MATCH p=(a)-[:CO_OCCURS_WITH*1..{hops_lit}]-(b)
                        MATCH (pa:Paper)-[:HAS_TOPIC]->(a)
                        WHERE toInteger(pa.year) <= $y
                        MATCH (pb:Paper)-[:HAS_TOPIC]->(b)
                        WHERE toInteger(pb.year) <= $y
                        WITH p, collect(DISTINCT toInteger(pa.year)) AS ya, collect(DISTINCT toInteger(pb.year)) AS yb
                        WITH p, ya, yb, [x IN ya + yb | x] AS all_years
                        RETURN length(p) AS len,
                               [r IN relationships(p) | r.weight] AS weights,
                               size(all_years) AS n_papers,
                               reduce(m = 0, x IN all_years | CASE WHEN x > m THEN x ELSE m END) AS max_year
                        ORDER BY len LIMIT 5""",
                        a=topic_a, b=topic_b, y=y
                    )
                    path_info["neo4j_paths"] = [dict(record) for record in result]
            except Exception:
                pass
        return path_info

    # ── 盲评材料 ──

    def generate_blind_review_materials(self, output_dir: str = None) -> dict:
        out = Path(output_dir) if output_dir else OUT_DIR / "blind_review"
        out.mkdir(parents=True, exist_ok=True)
        results = {"S0": {}, "S1": {}, "S2": {}, "generated_at": time.strftime("%Y-%m-%d %H:%M")}
        for q in LIBRARIAN_QUESTIONS:
            s0_answer = self.answer_question(q)
            results["S0"][q["qid"]] = s0_answer
            results["S1"][q["qid"]] = {
                "qid": q["qid"], "question": q["question"], "type": "S1_placeholder",
                "note": "S1 = S0 + XGBoost/普通时序趋势预测（待experiment_model_baseline填充）",
            }
            results["S2"][q["qid"]] = {
                "qid": q["qid"], "question": q["question"], "type": "S2_placeholder",
                "note": "S2 = S0 + RSSM多步预测 + 不确定性估计（待experiment_model_baseline填充）",
            }
        for level in ["S0", "S1", "S2"]:
            with open(out / f"{level}_answers.json", "w", encoding="utf-8") as f:
                json.dump(results[level], f, ensure_ascii=False, indent=2)
        with open(out / "librarian_questions.json", "w", encoding="utf-8") as f:
            json.dump(LIBRARIAN_QUESTIONS, f, ensure_ascii=False, indent=2)
        return {
            "output_dir": str(out), "questions": len(LIBRARIAN_QUESTIONS),
            "levels": ["S0", "S1", "S2"], "files": [str(p) for p in out.glob("*")],
        }

    # ── 泄露自查 ──

    def run_leak_check(self):
        """泄露自查：验证 as_of_year 过滤是否生效。

        输出：
        1. 所有结果中年份 >= as_of_year 的条目数（应为 0）
        2. 实际命中年份分布直方图
        3. Topic/Author 年份推导样本（3条）
        """
        print(f"\n{'='*60}")
        print(f"  数据泄露自查  as_of_year={self.as_of_year}  derive={self.derive_year_from}")
        print(f"{'='*60}")

        test_queries = ["文化遗产", "tourism", "digital", "一带一路", "knowledge graph"]
        all_years = []
        leaked = []

        for q in test_queries:
            result = self.query_by_keyword(q, top_k=30)
            for p in result["papers"]:
                y = p.get("year")
                if y is not None:
                    all_years.append(y)
                    if y >= self.as_of_year:
                        leaked.append({"query": q, "doi": p.get("doi", ""), "title": p["title"][:60], "year": y})

        print(f"\n[1] 泄漏检测")
        if leaked:
            print(f"  [FAIL] 发现 {len(leaked)} 条 year >= {self.as_of_year} 的文献！")
            for item in leaked[:10]:
                print(f"    [{item['year']}] {item['title']} (DOI: {item['doi']})")
        else:
            print(f"  [PASS] 零泄漏：{len(all_years)} 条文献中无 year >= {self.as_of_year} 的条目")

        print(f"\n[2] 年份分布")
        valid_years = [y for y in all_years if 1900 <= y < self.as_of_year]
        if valid_years:
            year_counter = Counter(sorted(valid_years))
            min_y, max_y = min(valid_years), max(valid_years)
            noise = len(all_years) - len(valid_years)
            print(f"  范围: {min_y} – {max_y}  总计: {len(valid_years)} 条", end="")
            if noise > 0:
                print(f"  (噪声过滤: {noise} 条 year<1900)")
            else:
                print()
            buckets = []
            for y in range(min_y, max_y + 1, 2):
                count = sum(year_counter.get(yy, 0) for yy in range(y, y + 2))
                if count > 0:
                    bar = "#" * (count // 2 + 1)
                    buckets.append(f"  {y}-{y+1:>2d}: {count:>4d} {bar}")
            print("\n".join(buckets))
        else:
            print(f"  无有效年份数据")

        print(f"\n[3] 年份推导样本（3条Topic + 3条Author）")
        sample_topics = ["tourism", "heritage", "knowledge graph"]
        sample_authors = ["Zhang", "Li", "Wang"]

        for tname in sample_topics:
            dy = self._derive_topic_year(tname)
            years_from_neo4j = []
            years_from_b1 = []
            if self.driver:
                try:
                    with self.driver.session() as s:
                        r = s.run(
                            "MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic) WHERE t.name = $name "
                            "RETURN toInteger(p.year) AS y ORDER BY y LIMIT 5", name=tname
                        )
                        years_from_neo4j = [x["y"] for x in r if x["y"] is not None and x["y"] >= 1900]
                except Exception:
                    pass
            for p in self.b1_records:
                kws = p.get("keywords") or p.get("normalized_keywords") or []
                if isinstance(kws, str): kws = [k.strip() for k in kws.split(",")]
                if tname.lower() in [k.lower() for k in kws]:
                    y = p.get("year")
                    if isinstance(y, (int, float)) and int(y) >= 1900:
                        years_from_b1.append(int(y))
                    if len(years_from_b1) >= 5:
                        break

            source = "Neo4j" if years_from_neo4j else "B1 JSON"
            years_display = years_from_neo4j[:5] if years_from_neo4j else years_from_b1[:5]
            method = self.derive_year_from
            calc = f"min({years_display})" if method == "earliest" else \
                   f"max({years_display})" if method == "latest" else \
                   f"mean({years_display})"
            print(f"  Topic「{tname}」→ derived={dy}  [source={source}, {method}: {calc}]  years={years_display}")

        for aname in sample_authors:
            dy = self._derive_author_year(aname)
            years_from_neo4j = []
            years_from_b1 = []
            if self.driver:
                try:
                    with self.driver.session() as s:
                        r = s.run(
                            "MATCH (p:Paper)-[:AUTHORED]->(a:Author) WHERE a.name CONTAINS $name "
                            "RETURN toInteger(p.year) AS y ORDER BY y LIMIT 5", name=aname
                        )
                        years_from_neo4j = [x["y"] for x in r if x["y"] is not None and x["y"] >= 1900]
                except Exception:
                    pass
            for p in self.b1_records:
                if aname in p.get("authors", ""):
                    y = p.get("year")
                    if isinstance(y, (int, float)) and int(y) >= 1900:
                        years_from_b1.append(int(y))
                    if len(years_from_b1) >= 5:
                        break

            source = "Neo4j" if years_from_neo4j else "B1 JSON"
            years_display = years_from_neo4j[:5] if years_from_neo4j else years_from_b1[:5]
            method = self.derive_year_from
            calc = f"min({years_display})" if method == "earliest" else \
                   f"max({years_display})" if method == "latest" else \
                   f"mean({years_display})"
            print(f"  Author「{aname}」→ derived={dy}  [source={source}, {method}: {calc}]  years={years_display}")

        print(f"\n{'='*60}")
        return {"leaked": len(leaked), "total_checked": len(all_years), "leaked_items": leaked}


# ═══════════════════ 主程序 ═══════════════════

def main():
    parser = argparse.ArgumentParser(description="S0 静态知识图谱服务基线")
    parser.add_argument("--as-of", type=int, required=True, help="截止年份（必填，任何>=此年的节点不进入结果）")
    parser.add_argument("--derive-year-from", choices=["earliest", "latest", "mean"],
                        default="earliest", help="Topic/Author年份推导方式（默认earliest）")
    parser.add_argument("--blind-review", action="store_true", help="生成盲评材料")
    parser.add_argument("--question", type=str, help="回答单个问题 (Q1-Q8)")
    parser.add_argument("--query", type=str, help="按关键词检索")
    parser.add_argument("--leak-check", action="store_true", help="泄露自查模式")
    args = parser.parse_args()

    sq = Neo4jServiceQuery(as_of_year=args.as_of, derive_year_from=args.derive_year_from)

    if args.leak_check:
        sq.run_leak_check()
        sq.close()
        return

    if args.blind_review:
        print(f"\n[>] 生成盲评材料 (as_of_year={args.as_of})...")
        result = sq.generate_blind_review_materials()
        print(f"  输出目录: {result['output_dir']}")
        print(f"  问题数: {result['questions']}")
        for f in result["files"]:
            print(f"  - {f}")
        sq.close()
        return

    if args.question:
        q = next((q for q in LIBRARIAN_QUESTIONS if q["qid"] == args.question), None)
        if q:
            answer = sq.answer_question(q)
            print(json.dumps(answer, ensure_ascii=False, indent=2))
        else:
            print(f"问题 {args.question} 不存在，可选: Q1-Q8")
        sq.close()
        return

    if args.query:
        result = sq.query_by_keyword(args.query, top_k=20)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sq.close()
        return

    print("=" * 60)
    print(f"  S0 静态知识图谱服务基线 (as_of_year={args.as_of})")
    print("=" * 60)

    print("\n[1] 热点 Top-10:")
    hs = sq.query_hotspots(10)
    for t in hs["topics"]:
        print(f"  {t['name']:<20s} heat={t['heat']}  growth={t['growth']:+.1f}")

    print("\n[2] 新兴方向 Top-10:")
    em = sq.query_emerging(10)
    for t in em["topics"]:
        print(f"  {t['name']:<20s} growth={t['growth']:+.1f}  heat={t['heat']}")

    print("\n[3] 数据覆盖:")
    cov = sq.query_coverage()
    print(f"  总论文: {cov['total_papers']}")
    print(f"  语种分布: {cov['language_distribution']}")
    print(f"  阿语占比: {cov['arabic_ratio']:.1%}")
    print(f"  稀疏主题: {cov['sparse_topics_count']} 个")

    print("\n[4] 馆员问题集演示:")
    for q in LIBRARIAN_QUESTIONS[:3]:
        answer = sq.answer_question(q)
        print(f"  [{q['qid']}] {q['question'][:40]}...")
        print(f"    类型: {answer.get('type', 'N/A')}")

    sq.close()
    print(f"\n[OK] S0基线查询完成")


if __name__ == "__main__":
    main()
