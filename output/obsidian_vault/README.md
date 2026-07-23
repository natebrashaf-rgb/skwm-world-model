# SKWM Obsidian 知识库 · 命名规范与使用指南

## 一、目录结构

```
obsidian_vault/
├── .obsidian/                  # Obsidian 配置
├── templates/                  # 5套笔记模板 (Templater)
├── 热点/                       # 研究热点笔记
├── 前沿/                       # 新兴前沿笔记
├── 问答/                       # GraphRAG 问答记录
├── 服务案例/                   # 学科服务案例
├── 术语/                       # 三语术语条目
└── attachments/                # 附件（图片等）
```

## 二、命名规范

| 笔记类型 | 命名格式 | 示例 |
|:---------|:---------|:-----|
| 研究热点 | `{year}_{中文主题}` | `2024_文化遗产旅游.md` |
| 新兴前沿 | `{year}_{中文主题}` | `2024_数字文旅.md` |
| 问答记录 | `QA_{问题摘要}_{ID前6位}` | `QA_文旅融合趋势分析_d4f8a2.md` |
| 服务案例 | `SC_{案例标题}` | `SC_文旅融合咨询.md` |
| 术语条目 | `术语_{中文名}` | `术语_文旅融合.md` |

**规则**：
- 文件名不含空格，使用下划线分隔
- 年份用 4 位数字
- 特殊字符用下划线替代
- 问答 ID 取 hash 前 6 位确保唯一

## 三、Tag 体系

| 标签 | 用途 | 层级 |
|:-----|:-----|:----:|
| `#hotspot` | 热点笔记 | 顶级 |
| `#frontier` | 前沿笔记 | 顶级 |
| `#qa` | 问答记录 | 顶级 |
| `#service-case` | 服务案例 | 顶级 |
| `#term` | 术语 | 顶级 |
| `#{year}` | 年份过滤 | 二级 |
| `#approved` / `#pending` | 审核状态 | 二级 |
| `#{domain}` | 领域（`#文旅` `#AI` `#文化遗产`） | 二级 |

## 四、双链约定

| 源 → 目标 | 链接写法 | 说明 |
|:----------|:---------|:-----|
| 问答 → 热点 | `[[2024_文化遗产旅游]]` | 直接引用热点笔记 |
| 问答 → 术语 | `[[术语_文旅融合]]` | 直接引用术语笔记 |
| 热点 → 前沿 | `[[2024_数字文旅]]` | 同级引用 |
| 服务案例 → 问答 | `[[QA_文旅融合趋势分析]]` | 源问答引用 |
| 术语 → 热点 | `[[2024_文化遗产旅游]]` | 反向引用 |

## 五、Dataview 查询示例

```dataview
# 查询所有 approved 的问答
TABLE confidence as "置信度", reviewer as "审核人"
FROM "问答"
WHERE contains(tags, "approved")
SORT confidence DESC
```

```dataview
# 查询与某个术语相关的所有笔记
LIST
FROM #term
WHERE contains(file.outlinks, [[术语_文旅融合]])
```

```dataview
# 查询 2024 年热点排行
TABLE heat_score as "热度", growth_rate as "增长率"
FROM "热点"
WHERE year = 2024
SORT heat_score DESC
```

## 六、自动化管线

```
GraphRAG 审核通过
       ↓
skwm_obsidian_export.py
       ↓
自动生成 Obsidian 笔记（带 YAML + 双链）
       ↓
放入 vault/问答/ 目录
       ↓
馆员在 Obsidian 中编辑/补充/关联
       ↓
可选：Git 同步到团队共享库
```

**运行导出**：
```bash
python skwm_obsidian_export.py
```

**Obsidian 设置**：
1. 打开 Obsidian → 打开本地仓库 → 选择 `output/obsidian_vault/`
2. 启用 Templater 插件，选择 `templates/` 为模板目录
3. 启用 Dataview 插件以运行查询
4. （可选）启用 Obsidian Git 自动同步

## 七、双链知识网可视化

Obsidian 的 Graph View（图谱视图）将显示：
- 热点 ↔ 前沿：同一主题的跨类型关联
- 问答 ↔ 热点：具体问题与宏观趋势的关联
- 问答 ↔ 术语：技术概念支撑
- 服务案例 ↔ 问答：服务流程与知识沉淀的闭环

Graph View 过滤建议：
- 按 `#qa` 查看问答知识网络
- 按 `#hotspot` 查看热点趋势图
- 全库查看 SKWM 完整知识网络
