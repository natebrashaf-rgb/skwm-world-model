# -*- coding: utf-8 -*-
"""
交叉验证脚本：源头数据 vs Neo4j 数据库
=====================================
验证方法（大白话）：
  数据库是"结果"，源头文件（主表/主题分配/PDF全文）是"原料"。
  我从原料重新算一遍应该得到什么，再和数据库里的实际数字对比。
  对上了 = 传输没丢没改；对不上 = 有问题，当场报出来。

源头文件：
  data/B1_文献主表.json        论文主表（标题/年份/作者/期刊/DOI）
  data/topic_assignments.json  主题分配结果（每篇论文匹配了哪些主题）
  data/pdf_texts.json          PDF 提取的全文
"""
import json
import re
import random
from collections import Counter
from neo4j import GraphDatabase

random.seed(20260803)  # 固定随机种子，保证每次抽查同一批，可复现

PASS, FAIL, WARN = [], [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗'} {name} {detail}")


def warn(name, detail=""):
    WARN.append(name)
    print(f"  ⚠ {name} {detail}")


# ========== 0. 读源头文件 ==========
print("=" * 60)
print("第 0 步：读源头文件（原料）")
print("=" * 60)

# 主表是脏 JSON：开头有个没键名的 _wm 标记，必须先剔掉
raw = open("data/B1_文献主表.json", encoding="utf-8").read()
clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
main = json.loads(clean)
print(f"  主表论文数: {len(main)}")

assign = json.load(open("data/topic_assignments.json", encoding="utf-8"))
print(f"  主题分配条数: {len(assign)}")

pdf_texts = json.load(open("data/pdf_texts.json", encoding="utf-8"))
print(f"  PDF 全文条数: {len(pdf_texts)}")

# ========== 1. 连数据库 ==========
print()
print("=" * 60)
print("第 1 步：从源头独立核算 + 数据库实际对比")
print("=" * 60)

drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "12345678"))
with drv.session() as s:
    # ---------- 1.1 论文总数 ----------
    print("\n[1] 论文")
    db_papers = s.run("MATCH (p:Paper) RETURN count(p) AS c").single()["c"]
    check("论文总数: 主表 vs 数据库", len(main) == db_papers,
          f"(主表 {len(main)} vs 库 {db_papers})")

    # ---------- 1.2 论文 DOI 完整性 ----------
    # 主表里每篇论文的 doi 应该在数据库里有对应的 Paper 节点
    main_dois = [p.get("doi", "").strip() for p in main]
    missing = []
    for doi in main_dois:
        if not doi:
            continue
        hit = s.run("MATCH (p:Paper {id: $d}) RETURN count(p) AS c", d=doi).single()["c"]
        if hit == 0:
            missing.append(doi)
    check("论文DOI全部入库", len(missing) == 0, f"(缺 {len(missing)} 篇)")
    if missing[:3]:
        warn("缺失DOI样例", missing[:3])

    # ---------- 1.3 抽查 10 篇论文的标题/年份 ----------
    sample = random.sample(main, 10)
    print("\n[2] 抽查 10 篇论文（标题/年份是否原样入库）")
    mismatch = 0
    for p in sample:
        doi = p.get("doi", "")
        row = s.run("MATCH (p:Paper {id: $d}) RETURN p.title AS t, p.year AS y",
                    d=doi).single()
        if row is None:
            mismatch += 1
            print(f"    ✗ {doi} 数据库里没有")
            continue
        ok = (row["t"] == p.get("title")) and (row["y"] == p.get("year"))
        if not ok:
            mismatch += 1
            print(f"    ✗ {doi} 主表[{p.get('title')[:40]}] vs 库[{row['t'][:40]}]")
    check("抽查10篇标题年份一致", mismatch == 0, f"(不一致 {mismatch} 篇)")

    # ---------- 1.4 作者 ----------
    print("\n[3] 作者")
    db_authors = s.run("MATCH (a:Author) RETURN count(a) AS c").single()["c"]
    db_authored = s.run("MATCH ()-[r:AUTHORED]->() RETURN count(r) AS c").single()["c"]
    # 从主表拆分作者
    author_names = set()
    authored_pairs = 0
    for p in main:
        auth_str = p.get("authors") or ""
        names = [x.strip() for x in auth_str.split(",") if x.strip()]
        authored_pairs += len(names)
        author_names.update(names)
    check("作者节点数: 主表去重 vs 库", len(author_names) == db_authors,
          f"(主表 {len(author_names)} vs 库 {db_authors})")
    check("作者关系数: 主表配对 vs 库", authored_pairs == db_authored,
          f"(主表 {authored_pairs} vs 库 {db_authored})")

    # ---------- 1.5 期刊 ----------
    print("\n[4] 期刊")
    db_venues = s.run("MATCH (v:Venue) RETURN count(v) AS c").single()["c"]
    db_pub = s.run("MATCH ()-[r:PUBLISHED_IN]->() RETURN count(r) AS c").single()["c"]
    venue_names = set()
    pub_pairs = 0
    for p in main:
        v = (p.get("venue") or "").strip()
        if v:
            venue_names.add(v)
            pub_pairs += 1
    check("期刊节点数: 主表去重 vs 库", len(venue_names) == db_venues,
          f"(主表 {len(venue_names)} vs 库 {db_venues})")
    check("发表关系数: 主表 vs 库", pub_pairs == db_pub,
          f"(主表 {pub_pairs} vs 库 {db_pub})")

    # ---------- 1.6 年份 ----------
    print("\n[5] 年份")
    db_years = s.run("MATCH (y:Year) RETURN count(y) AS c").single()["c"]
    db_yr = s.run("MATCH ()-[r:PUBLISHED_IN_YEAR]->() RETURN count(r) AS c").single()["c"]
    years = set()
    yr_pairs = 0
    for p in main:
        y = p.get("year")
        if y:
            years.add(y)
            yr_pairs += 1
    check("年份节点数: 主表去重 vs 库", len(years) == db_years,
          f"(主表 {len(years)} vs 库 {db_years})")
    check("年份关系数: 主表 vs 库", yr_pairs == db_yr,
          f"(主表 {yr_pairs} vs 库 {db_yr})")

    # ---------- 1.7 主题 ----------
    print("\n[6] 主题")
    db_topics = s.run("MATCH (t:Topic) RETURN count(t) AS c").single()["c"]
    db_has = s.run("MATCH ()-[r:HAS_TOPIC]->() RETURN count(r) AS c").single()["c"]
    # 从 assignments 核算：matched 的论文，terms 里的主题
    topic_names = set()
    has_pairs = 0
    matched_papers = 0
    for doi, info in assign.items():
        if info.get("matched"):
            matched_papers += 1
            for t in info.get("terms", []):
                topic_names.add(t)
                has_pairs += 1
    check("主题节点数: assignments去重 vs 库", len(topic_names) == db_topics,
          f"(assignments {len(topic_names)} vs 库 {db_topics})")
    check("主题关系数: assignments vs 库", has_pairs == db_has,
          f"(assignments {has_pairs} vs 库 {db_has})")
    check("命中论文数=7796", matched_papers == 7796, f"(实际 {matched_papers})")

    # ---------- 1.8 领域 ----------
    print("\n[7] 领域")
    db_domains = s.run("MATCH (d:Domain) RETURN count(d) AS c").single()["c"]
    db_bel = s.run("MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) AS c").single()["c"]
    domains = set()
    bel_pairs = 0
    for doi, info in assign.items():
        for d in info.get("domains", []):
            domains.add(d)
            bel_pairs += 1
    check("领域节点数: assignments去重 vs 库", len(domains) == db_domains,
          f"(assignments {len(domains)} vs 库 {db_domains})")
    check("领域关系数: assignments vs 库", bel_pairs == db_bel,
          f"(assignments {bel_pairs} vs 库 {db_bel})")

    # ---------- 1.9 共现关系（核心！） ----------
    print("\n[8] 主题共现（关键验证）")
    db_coc = s.run("MATCH ()-[r:CO_OCCURS_WITH]->() RETURN count(r) AS c").single()["c"]
    # 从 assignments 独立核算：同一篇论文里出现的主题两两成对
    pair_counter = Counter()
    for doi, info in assign.items():
        terms = sorted(set(info.get("terms", [])))
        for i in range(len(terms)):
            for j in range(i + 1, len(terms)):
                pair_counter[(terms[i], terms[j])] += 1
    unique_pairs = len(pair_counter)
    total_weight = sum(pair_counter.values())
    check("共现关系数: 核算 vs 库", unique_pairs == db_coc,
          f"(核算无向对 {unique_pairs} vs 库 {db_coc})")
    # 最强共现抽查：库里的前 5 大共现应该和核算一致
    db_top5 = [(r["a"], r["b"], r["w"]) for r in s.run(
        "MATCH (a:Topic)-[r:CO_OCCURS_WITH]->(b:Topic) "
        "RETURN a.name AS a, b.name AS b, r.weight AS w "
        "ORDER BY r.weight DESC LIMIT 5")]
    calc_top5 = [(k[0], k[1], v) for k, v in pair_counter.most_common(5)]
    top5_ok = all(any(a == ca and b == cb for ca, cb, _ in calc_top5) for a, b, _ in db_top5)
    check("最强共现前5一致", top5_ok, f"(库: {[(a,b,w) for a,b,w in db_top5]})")

    # ---------- 1.10 孤立节点 ----------
    print("\n[9] 结构健康")
    iso = s.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) AS c").single()["c"]
    check("孤立节点=0", iso == 0, f"(实际 {iso})")
    # 主题里有没有完全无共现的孤立主题
    iso_topics = s.run(
        "MATCH (t:Topic) WHERE NOT (t)-[:CO_OCCURS_WITH]-() RETURN count(t) AS c"
    ).single()["c"]
    warn("无共现边的主题数（共现图会散落）", f"(实际 {iso_topics})")

    # ---------- 1.11 垃圾词 ----------
    print("\n[10] 垃圾词检查")
    junk = s.run(
        "MATCH (t:Topic) WHERE t.name IN ['as an','of an','clinical','gene',"
        "'in chinese','an introduction','guidelines','standard'] "
        "RETURN count(t) AS c").single()["c"]
    check("v1垃圾词=0", junk == 0, f"(实际 {junk})")

drv.close()

# ========== 结果汇总 ==========
print()
print("=" * 60)
print(f"结果: {len(PASS)} 通过, {len(FAIL)} 失败, {len(WARN)} 提醒")
print("=" * 60)
if FAIL:
    print("【失败项（需要处理）】")
    for f in FAIL:
        print("  ✗", f)
if WARN:
    print("【提醒项（非错误，但要知道）】")
    for w in WARN:
        print("  ⚠", w)
if not FAIL:
    print("全部核心检查通过。")
