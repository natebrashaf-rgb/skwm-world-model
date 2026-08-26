# 复核证据索引（2026-08-27）

回应第 2 轮只读复核的「仍无证据」项。证据分三类：已 push 仓库、本地产出目录（可转交）、无法复原（如实说明）。

## 一、已 push GitHub（本目录/仓库内）
| 证据 | 对应复核项 |
|------|-----------|
| data/复核证据_20260827/主表差分_12177vs12233.json | +56 数据来源与逐条差异（54 键差 + 2 键冲突内容不同，含 DOI/标题/来源/语种） |
| data/复核证据_20260827/主题差分_20260827.md | Topic +1（'Local Economy'）与合并后 -60/+57 全清单 |
| data/复核证据_20260827/state_vectors_新旧对比_20260827.md | 新版 43642/83年/1912 起 vs 旧版 43768/89年/1895 起，代码未变 |
| data/复核证据_20260827/domain_词表证据_20260827.md | Domain 单字/符号来源更正（字符串 domains 拆字符，非词表问题） |
| data/复核证据_20260827/hamza_逐条命中_20260827.md | hamza 归一化 27 条逐条（title 19 / fulltext 8） |
| data/query_fields_facts_stdout_20260827.txt | query_fields_facts.py 完整 stdout |
| data/leak_check_stdout_20260827.txt | neo4j_service_query.py --leak-check 输出（零泄漏 PASS） |
| data/gexf_验证报告_20260827_v2.md + 2 PNG | GEXF v2（合并后）networkx 读回验证 + 渲染 |
| data/_enhance_arabic_dryrun.json | 阿语 dry-run 逐条新旧 terms（18:37 生成版） |
| scripts/export_gexf_20260827_v2.py | GEXF v2 导出脚本 |
| scripts/fix_str_typed_entries.py | 11 条字符串修复脚本 |
| scripts/apply_arabic_enhance.py | 阿语合并脚本 |
| scripts/enhance_arabic_assignments.py | dry-run v2 脚本 |
| scripts/build_snapshot_20260827.py | 快照导出脚本（合并后元数据） |
| neo4j_service_query.py | 查询改造（--as-of 必填/--leak-check/--blind-review/--question） |

## 二、本地产出目录（E:\大挑\产出\重建_20260826\，供转交复核者）
| 文件 | 大小 | SHA-256 | 对应复核项 |
|------|------|---------|-----------|
| backup/topic_assignments.bak_20260826_184708.json | 3376083 | b2060ae7…（合并前） | 合并前后 assignments 逐条复算 |
| backup/topic_assignments.bak_strfix_20260826_191136.json | — | —（修复前） | 11 条修复前 |
| backup/state_vectors_bak_20260826_175743.json | 3048038 | 见 sha256_manifest.csv | 旧版 state_vectors |
| backup/B1_文献主表_bak_20260826_175743.json | 6522548 | — | 8/19 版主表（12177） |
| knowledge_graph_20260827_v2.gexf | 18.0MB | 见下 | 合并后 GEXF（大文件不入仓库） |
| knowledge_graph_20260827.gexf | 18.9MB | b3e83b47 对应版 | 合并前 GEXF（复核已解析的那份） |
| 重建日志.md | — | — | 红线3/红线4 全部命令+时间+结果 |

GEXF v2 SHA-256：bc83c3515ffabfe22956818e27a9e9d818978580f1aca2b62d66ed1aab5c398e（18.0MB，合并后）

## 三、无法复原（如实说明）
| 项 | 说明 |
|----|------|
| 8/26 18:01 audit_neo4j.py 原始 stdout | 当时未存文件，终端输出已消失；书面记录在重建日志红线4（五数表 12233/1174/114473/0/0）与 19:08 HTTP API 实测 |
| 8/19→8/21 合并时 match_topics.py 退化版 assignments | 回滚已覆盖，退化版未留存；回滚后版本=b2060ae7（backup 有） |
| 8/19 原始阿语增强脚本 | 已确认不存在（全盘搜索无果），按产物推断存在字符拆分缺陷 |

## 四、时间线澄清（复核的"版本矛盾"）
- 18:47-18:51 合并阶段：只改文件，图库未重建 → 日志红线3 写「图库未重建，实测 114473」——当时状态，正确
- 19:00-19:01 rebuild：图库重建 → 114845 / Topic 1168（红线4 记录）
- 19:09 快照导出：合并后口径 114845 / 1168
- 两个数字对应不同时点，非矛盾；复核者若只看红线3 段落会误读，已在重建日志加时间线说明
