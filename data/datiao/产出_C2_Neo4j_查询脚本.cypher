// ====== 中阿文旅知识图谱 · Neo4j 导入与查询脚本 ======
// 使用前提：已安装 Neo4j Desktop 或 Docker 运行 Neo4j
// 运行: neo4j-admin import 或 cypher-shell -f 本文件

// ---- 创建约束 ----
CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE;

// ---- 导入节点（示例 - 实际数据从CSV批量导入） ----
// :auto LOAD CSV FROM 'file:///nodes_paper.csv' AS row
// CREATE (:Paper {id: row[0], title: row[1], year: toInteger(row[2]), doi: row[3]});

// ---- 示例查询 1：主题→文献 ----
// 查询研究"旅游"主题的所有论文

MATCH (p:Paper)-[:studies]->(t:Topic)
WHERE t.name CONTAINS 'Tourism'
RETURN p.title, p.year, t.name
LIMIT 20;

// ---- 示例查询 2：作者→合作者 ----
// 查询某个作者的合作者网络
MATCH (a1:Author)-[:authored_by]-(p:Paper)-[:authored_by]-(a2:Author)
WHERE a1.name = 'Zhang Wei'
RETURN a2.name AS collaborator, count(p) AS collaborations
ORDER BY collaborations DESC
LIMIT 10;

// ---- 示例查询 3：关键词→共现Top 10 ----
// 查询与"文化遗产"共现最多的关键词
// 注：该查询需要先导入共现表 (B2_共现表.csv)
// :auto LOAD CSV FROM 'file:///cooccur.csv' AS row
// MATCH (k1:Keyword {name: row[0]}), (k2:Keyword {name: row[1]})
// CREATE (k1)-[:CO_OCCUR {weight: toInteger(row[2])}]->(k2);

MATCH (k:Keyword {name: '文化遗产'})-[r:CO_OCCUR]->(other:Keyword)
RETURN other.name AS co_occur_term, r.weight AS frequency
ORDER BY frequency DESC
LIMIT 10;
