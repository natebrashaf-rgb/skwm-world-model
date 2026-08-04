# -*- coding: utf-8 -*-
"""
图数据库重建验证脚本
查：节点数/关系数/孤立节点/主题质量/抽样
"""
from neo4j import GraphDatabase

CREDS = {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "12345678"}


def q(driver, label, query):
    with driver.session() as s:
        res = s.run(query).data()
        print(f"\n=== {label} ===")
        for r in res:
            print("  ", " | ".join(f"{k}: {v}" for k, v in r.items()))


def main():
    driver = GraphDatabase.driver(CREDS["uri"], auth=(CREDS["user"], CREDS["password"]))
    driver.verify_connectivity()
    print("[OK] 已连接")

    q(driver, "节点总数", "MATCH (n) RETURN count(n) AS 节点总数")
    q(driver, "各标签节点数", "MATCH (n) RETURN labels(n) AS 标签, count(*) AS 数量 ORDER BY 数量 DESC")
    q(driver, "关系总数", "MATCH ()-[r]->() RETURN count(r) AS 关系总数")
    q(driver, "各类型关系数", "MATCH ()-[r]->() RETURN type(r) AS 类型, count(*) AS 数量 ORDER BY 数量 DESC")
    q(driver, "完全孤立节点", "MATCH (n) WHERE NOT (n)--() RETURN labels(n) AS 标签, count(*) AS 孤立数")
    q(driver, "无主题论文", "MATCH (p:Paper) WHERE NOT (p)-[:HAS_TOPIC]->() RETURN count(p) AS 无主题论文数")
    q(driver, "平均每篇论文主题数", "MATCH (p:Paper)-[:HAS_TOPIC]->(t) RETURN count(t) * 1.0 / count(DISTINCT p) AS 平均主题数")
    q(driver, "最热主题 Top 15", "MATCH (t:Topic)<-[:HAS_TOPIC]-(p:Paper) RETURN t.name AS 主题, count(p) AS 论文数 ORDER BY 论文数 DESC LIMIT 15")
    q(driver, "最强共现 Top 15", "MATCH (a:Topic)-[r:CO_OCCURS_WITH]->(b:Topic) RETURN a.name AS 主题A, b.name AS 主题B, r.weight AS 共现强度 ORDER BY 共现强度 DESC LIMIT 15")
    q(driver, "领域分布", "MATCH (d:Domain)<-[:BELONGS_TO_DOMAIN]-(p:Paper) RETURN d.name AS 领域, count(p) AS 论文数 ORDER BY 论文数 DESC")
    q(driver, "近年主题热度抽样(2020-2025)",
      "MATCH (t:Topic)-[r:SNAPSHOT]->(y:Year) WHERE y.year >= 2020 RETURN y.year AS 年份, count(DISTINCT t) AS 活跃主题数, sum(r.heat) AS 论文热度 ORDER BY 年份")

    driver.close()
    print("\n[完成] 验证结束")


if __name__ == "__main__":
    main()
