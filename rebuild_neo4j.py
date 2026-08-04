# -*- coding: utf-8 -*-
"""
SKWM 图数据库重建脚本 v2.0
输入:
  - B1_文献主表.json        (论文元数据)
  - topic_assignments.json  (受控词表匹配结果: 论文→主题/领域)
  - pdf_texts.json          (PDF全文, 可选: 用于补充匹配)
输出: Neo4j 图（清空重建）
  节点: Paper / Author / Venue / Year / Topic / Domain
  关系: AUTHORED / PUBLISHED_IN / PUBLISHED_IN_YEAR / HAS_TOPIC / BELONGS_TO_DOMAIN
        CO_OCCURS_WITH (主题共现, weight=同现论文数) / SNAPSHOT (主题-年份热度)
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

from neo4j import GraphDatabase

DATA_DIR = r"E:\大挑\rail_deploy\data"
MAIN_TABLE = os.path.join(DATA_DIR, "B1_文献主表.json")
ASSIGNMENTS = os.path.join(DATA_DIR, "topic_assignments.json")
PDF_TEXTS = os.path.join(DATA_DIR, "pdf_texts.json")
CRED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".neo4j_cred.json")


def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def load_creds():
    if not os.path.exists(CRED_FILE):
        sys.exit(f"[错误] 找不到连接文件 {CRED_FILE}")
    with open(CRED_FILE, encoding="utf-8") as f:
        return json.load(f)


def split_authors(authors: str):
    if not authors:
        return []
    parts = re.split(r"[,;，；、]|\s+and\s+|\s+&\s+", authors)
    return [p.strip() for p in parts if p.strip()]


def normalize_title(t):
    """标题规范化（用于 PDF 文件名匹配）"""
    t = (t or "").lower()
    t = re.sub(r"^[\d_\.\-\s]+", "", t)           # 去序号前缀
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)  # 非字母数字转空格
    return re.sub(r"\s+", " ", t).strip()


def main():
    creds = load_creds()
    driver = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))
    driver.verify_connectivity()
    print("[OK] 已连接 Neo4j:", creds["uri"])

    # 1. 加载
    print("[1/6] 加载数据...")
    papers = load_skwm_json(MAIN_TABLE)
    papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    assigns = json.load(open(ASSIGNMENTS, encoding="utf-8"))
    pdf_texts = {}
    if os.path.exists(PDF_TEXTS):
        pdf_texts = json.load(open(PDF_TEXTS, encoding="utf-8"))
    print(f"    论文 {len(papers)} | 匹配结果 {len(assigns)} | PDF全文 {len(pdf_texts)}")

    # 2. 建立 论文id → 主题/领域 映射（标题匹配结果为准）
    paper_topics = {}   # pid -> set(主题词)
    paper_domains = {}  # pid -> set(领域)
    for pid, v in assigns.items():
        if v.get("matched"):
            paper_topics[pid] = set(v.get("terms", []))
            paper_domains[pid] = set(v.get("domains", []))

    # 3. PDF 文件名 → 主表论文 对应（模糊匹配），补充全文匹配结果
    print("[2/6] PDF 文件名 ↔ 主表 对应...")
    norm_title_to_pid = {}
    for p in papers:
        pid = str(p.get("doi") or p.get("title"))[:200]
        norm_title_to_pid.setdefault(normalize_title(p.get("title")), pid)
    pdf_matched = 0
    for fname, ftext in pdf_texts.items():
        if not ftext:
            continue
        nf = normalize_title(fname)
        # 前缀/包含匹配：文件名是标题的前缀或核心部分
        pid = None
        if nf in norm_title_to_pid:
            pid = norm_title_to_pid[nf]
        else:
            # 文件名前40字符 vs 标题前40字符
            pre40 = nf[:40]
            for t, tp in norm_title_to_pid.items():
                if pre40 and (t.startswith(pre40) or pre40.startswith(t[:25]) and len(t) > 20):
                    pid = tp
                    break
        if pid:
            pdf_matched += 1
    print(f"    PDF↔主表 匹配: {pdf_matched}/{len(pdf_texts)}")

    # 4. 构建批量数据
    print("[3/6] 构建批量数据...")
    paper_rows = []
    topic_papers = defaultdict(set)   # topic -> papers
    domain_papers = defaultdict(set)  # domain -> papers
    co_occur = Counter()              # (t1,t2) -> count
    year_topic = Counter()            # (year, topic) -> count
    for p in papers:
        pid = str(p.get("doi") or p.get("title"))[:200]
        year = p.get("year") or 0
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = 0
        venue = (p.get("venue") or "").strip() or "未知"
        paper_rows.append({
            "pid": pid, "title": p.get("title", ""), "year": year,
            "citations": p.get("citations", 0), "venue": venue,
            "authors": split_authors(p.get("authors", "")),
        })
        topics = paper_topics.get(pid, set())
        domains = paper_domains.get(pid, set())
        for t in topics:
            topic_papers[t].add(pid)
            year_topic[(year, t)] += 1
        for d in domains:
            domain_papers[d].add(pid)
        tlist = sorted(topics)
        for i in range(len(tlist)):
            for j in range(i + 1, len(tlist)):
                co_occur[(tlist[i], tlist[j])] += 1

    # 5. 写入
    with driver.session() as s:
        print("[4/6] 清空旧库...")
        s.run("MATCH (n) DETACH DELETE n")

        print("[5/6] 写入论文子图...")
        for bi in range(0, len(paper_rows), 500):
            chunk = paper_rows[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MERGE (p:Paper {id: r.pid})
            SET p.title = r.title, p.year = r.year, p.citations = r.citations
            MERGE (v:Venue {name: r.venue})
            MERGE (p)-[:PUBLISHED_IN]->(v)
            MERGE (y:Year {year: r.year})
            MERGE (p)-[:PUBLISHED_IN_YEAR]->(y)
            FOREACH (a IN r.authors |
                MERGE (au:Author {name: a})
                MERGE (au)-[:AUTHORED]->(p)
            )
            """, rows=chunk)
        print(f"    论文 {len(paper_rows)} 已写入")

        print("[6/6] 写入主题/领域/共现/时序...")
        # 主题节点 + HAS_TOPIC
        topic_rows = [{"t": t} for t in sorted(topic_papers)]
        for bi in range(0, len(topic_rows), 500):
            chunk = topic_rows[bi:bi + 500]
            s.run("UNWIND $rows AS r MERGE (t:Topic {name: r.t})", rows=chunk)
        # 领域节点
        dom_rows = [{"d": d} for d in sorted(domain_papers)]
        for bi in range(0, len(dom_rows), 500):
            chunk = dom_rows[bi:bi + 500]
            s.run("UNWIND $rows AS r MERGE (d:Domain {name: r.d})", rows=chunk)
        # HAS_TOPIC + BELONGS_TO_DOMAIN（按论文批量）
        link_rows = []
        for pid, topics in paper_topics.items():
            for t in topics:
                link_rows.append({"pid": pid, "t": t})
        for bi in range(0, len(link_rows), 500):
            chunk = link_rows[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MATCH (p:Paper {id: r.pid})
            MATCH (t:Topic {name: r.t})
            MERGE (p)-[:HAS_TOPIC]->(t)
            """, rows=chunk)
        for pid, domains in paper_domains.items():
            for d in domains:
                s.run("MATCH (p:Paper {id: $pid}) MATCH (d:Domain {name: $d}) MERGE (p)-[:BELONGS_TO_DOMAIN]->(d)",
                      pid=pid, d=d)
        print(f"    HAS_TOPIC {len(link_rows)} | BELONGS_TO_DOMAIN {sum(len(v) for v in paper_domains.values())}")

        # 共现边
        co_rows = [{"a": a, "b": b, "w": c} for (a, b), c in co_occur.items()]
        for bi in range(0, len(co_rows), 500):
            chunk = co_rows[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MATCH (a:Topic {name: r.a}) MATCH (b:Topic {name: r.b})
            MERGE (a)-[rel:CO_OCCURS_WITH]->(b)
            SET rel.weight = r.w
            """, rows=chunk)
        print(f"    共现边 {len(co_rows)}")

        # SNAPSHOT 时序（每年每主题论文数）
        snap_rows = [{"t": t, "y": y, "heat": c} for (y, t), c in year_topic.items()]
        for bi in range(0, len(snap_rows), 500):
            chunk = snap_rows[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MATCH (t:Topic {name: r.t}) MATCH (y:Year {year: r.y})
            MERGE (t)-[rel:SNAPSHOT]->(y)
            SET rel.heat = r.heat
            """, rows=chunk)
        print(f"    SNAPSHOT 时序 {len(snap_rows)}")

    driver.close()
    print("\n[完成] 图数据库重建成功！")
    print(f"主题数 {len(topic_papers)} | 领域数 {len(domain_papers)} | 共现边 {len(co_rows)} | 时序 {len(snap_rows)}")


if __name__ == "__main__":
    main()
