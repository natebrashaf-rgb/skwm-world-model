"""
SKWM 图数据库 ETL — 数据 → Neo4j
输入: B1文献主表 / state_vectors / temporal_snapshots / term_alignment
输出: Neo4j 图（Paper/Author/Topic/Institution/Method/Venue/Year 节点 + 关系）
连接信息从私有文件读取（不硬编码）
"""
import json
import os
import re
import sys
from collections import Counter

from neo4j import GraphDatabase

DATA_DIR = r"E:\大挑\rail_deploy\data"
CRED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".neo4j_cred.json")


def load_skwm_json(path):
    """兼容带 _wm 前缀的 JSON 文件"""
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def load_creds():
    """读取连接信息：优先 .neo4j_cred.json（本地/云端通用）"""
    if not os.path.exists(CRED_FILE):
        sys.exit(f"[错误] 找不到连接文件 {CRED_FILE}\n请先创建: "
                 f'{{"uri": "bolt://localhost:7687", "user": "neo4j", "password": "12345678"}}')
    with open(CRED_FILE, encoding="utf-8") as f:
        return json.load(f)


def split_authors(authors: str):
    """作者字符串 → 列表（按逗号/分号/和 分割）"""
    if not authors:
        return []
    parts = re.split(r"[,;，；、]|\s+and\s+|\s+&\s+", authors)
    return [p.strip() for p in parts if p.strip()]


def main():
    creds = load_creds()
    driver = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))
    driver.verify_connectivity()
    print("[OK] 已连接 Neo4j:", creds["uri"])

    # 1. 加载数据
    print("[1/5] 加载数据...")
    papers = load_skwm_json(os.path.join(DATA_DIR, "B1_文献主表.json"))
    sv = json.load(open(os.path.join(DATA_DIR, "state_vectors.json"), encoding="utf-8"))
    ts = json.load(open(os.path.join(DATA_DIR, "temporal_snapshots.json"), encoding="utf-8"))
    # temporal_snapshots 顶层可能混有 _wm 伪键或非 dict 值，过滤掉
    ts = {k: v for k, v in ts.items() if isinstance(v, dict) and k != "_wm"}
    # 文献主表第一个元素可能是 _wm 伪记录，过滤掉非 dict 或没有 title/doi 的
    papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    print(f"    文献: {len(papers)} | 状态向量年份: {len(sv)} | 时序快照: {len(ts)}")

    # 2. 统计
    venues = Counter(p.get("venue", "") or "未知" for p in papers)
    years = Counter(p.get("year") or 0 for p in papers)
    print(f"    Venue 数: {len(venues)} | 年份数: {len(years)}")

    with driver.session() as s:
        # 3. 建约束（幂等）
        print("[2/5] 创建约束...")
        for label, prop in [("Paper", "id"), ("Author", "name"), ("Topic", "name"),
                            ("Venue", "name"), ("Year", "year"), ("Institution", "name"),
                            ("Method", "name")]:
            s.run(f"CREATE CONSTRAINT {label.lower()}_{prop} IF NOT EXISTS "
                  f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
        print("    完成")

        # 4. 批量写文献 + 作者/主题/期刊/年份节点 + 关系
        print("[3/5] 写入文献子图...")
        batch = []
        for i, p in enumerate(papers):
            pid = p.get("doi") or p.get("title")
            if not pid:
                continue
            pid = str(pid)[:200]
            year = p.get("year") or 0
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = 0
            venue = (p.get("venue") or "").strip() or "未知"
            keywords = p.get("normalized_keywords") or p.get("keywords") or []
            batch.append({
                "pid": pid, "title": p.get("title", ""), "year": year,
                "citations": p.get("citations", 0), "venue": venue,
                "authors": split_authors(p.get("authors", "")),
                "keywords": keywords,
            })
        # 分批写入，每批 500
        for bi in range(0, len(batch), 500):
            chunk = batch[bi:bi + 500]
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
            FOREACH (k IN r.keywords |
                MERGE (t:Topic {name: k})
                MERGE (p)-[:HAS_TOPIC]->(t)
            )
            """, rows=chunk)
        print(f"    已写入 {len(batch)} 篇文献")

        # 5. 写入时序状态向量 (Year 节点 + SNAPSHOT 关系) — 批量 UNWIND 加速
        print("[4/5] 写入时序状态向量...")
        sv_batch = []
        for y, ents in sv.items():
            if y == "_wm" or not isinstance(ents, dict):
                continue
            y = int(y)
            for name, vec in ents.items():
                heat = vec[0] if len(vec) > 0 else 0
                growth = vec[1] if len(vec) > 1 else 0
                central = vec[2] if len(vec) > 2 else 0
                sv_batch.append({"name": name, "y": y, "heat": heat,
                                 "growth": growth, "central": central})
        for bi in range(0, len(sv_batch), 500):
            chunk = sv_batch[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MERGE (t:Topic {name: r.name})
            MERGE (y:Year {year: r.y})
            MERGE (t)-[rel:SNAPSHOT]->(y)
            SET rel.heat = r.heat, rel.growth = r.growth, rel.centrality = r.central
            """, rows=chunk)
        print(f"    已写入 {len(sv_batch)} 条时序状态")

        # 6. 写入时序共现边 (TemporalSnapshot 关系) — 按 (a,b) 唯一，weight 累加，years 收集
        print("[5/5] 写入时序共现边...")
        edge_map = {}  # (u,v) -> {"w": 累加权重, "years": []}
        for y, snap in ts.items():
            if y == "_wm" or not isinstance(snap, dict):
                continue
            y = int(y)
            for e in snap.get("edges", []):
                u, v, w = e.get("u"), e.get("v"), e.get("w", 1)
                if not u or not v:
                    continue
                key = (u, v)
                if key not in edge_map:
                    edge_map[key] = {"w": 0, "years": []}
                edge_map[key]["w"] += w
                if y not in edge_map[key]["years"]:
                    edge_map[key]["years"].append(y)
        edge_batch = [
            {"u": u, "v": v, "w": d["w"], "years": d["years"]}
            for (u, v), d in edge_map.items()
        ]
        for bi in range(0, len(edge_batch), 500):
            chunk = edge_batch[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MERGE (a:Topic {name: r.u})
            MERGE (b:Topic {name: r.v})
            MERGE (a)-[rel:CO_OCCURS_WITH]->(b)
            SET rel.weight = r.w, rel.years = r.years
            """, rows=chunk)
        print(f"    已写入 {len(edge_batch)} 条共现边（唯一对，权重跨年累加）")

    driver.close()
    print("\n[完成] 图数据库构建成功！")


if __name__ == "__main__":
    main()
