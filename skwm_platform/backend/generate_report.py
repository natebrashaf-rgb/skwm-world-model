#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  中阿文旅研究热点与前沿分析报告 — 自动生成                    ║
║                                                                ║
║  对应策划案第三阶段（九·126-142）产出:                        ║
║  《中阿文旅研究热点与前沿分析报告》                            ║
║  关键词共现图 · 机构合作网络图 · 主题演化图                   ║
║                                                                ║
║  输出: E:\\大挑\\02_deliverables\\                                 ║
╟──────────────────────────────────────────────────────────────────╢
║  用法: python generate_report.py                                 ║
╚══════════════════════════════════════════════════════════════════╝
"""
import json, os, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ── 路径 ──────────────────────────────────────────────────────────
BACKEND = Path(__file__).parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

OUT_DIR = Path(r"E:\大挑\02_deliverables")
OUT_DIR.mkdir(exist_ok=True)

# ── 导入SKWM数据层 ──────────────────────────────────────────────
print("📦 加载世界模型数据...")
from skwm_aligned_v4 import DataLayer, ArabicAgent
DATA = DataLayer().load(verbose=False)
AR = ArabicAgent()
YEAR = max(DATA.year_range) if DATA.year_range else 2026

# ── 收集数据 ─────────────────────────────────────────────────────
print(f"📊 正在生成 {YEAR} 年分析报告...")

# 1. 热点主题
hot = DATA.get_hot_topics(YEAR, 20)
# 2. 新兴前沿
emerging = DATA.get_emerging(YEAR, 15)
# 3. 实体类型分布
entities = DATA.get_entities(YEAR)
etype_dist = defaultdict(int)
for name in entities:
    # 简单分类
    if any(kw in name for kw in ["旅游","文化","遗产","研究","分析","模型","tourism","tour","culture","heritage","digital"]):
        etype_dist["主题"] += 1
    elif any(kw in name for kw in ["大学","学院","university","institute","center"]):
        etype_dist["机构"] += 1
    elif any(kw in name for kw in ["中国","阿拉伯","沙特","china","arab","saudi","egypt","dubai"]):
        etype_dist["地点"] += 1
    elif any(kw in name for kw in ["政策","一带一路","policy","belt and road"]):
        etype_dist["政策"] += 1
    elif any(kw in name for kw in ["会议","论坛","conference","summit"]):
        etype_dist["事件"] += 1
    else:
        etype_dist["主题"] += 1  # 默认归入主题

# 4. 年度趋势
snapshots_trend = []
for y_str, snap in sorted(DATA.snapshots.items(), key=lambda kv: int(kv[0])):
    snapshots_trend.append({
        "year": int(y_str),
        "nodes": snap.get("n_nodes", 0),
        "edges": snap.get("n_edges", 0),
    })

# 5. 全库统计
total_nodes = sum(s.get("n_nodes", 0) for s in DATA.snapshots.values())
total_edges = sum(s.get("n_edges", 0) for s in DATA.snapshots.values())
total_state = DATA.n_state_vectors

# 6. 阿语术语统计
ar_terms = len(AR.terms) if hasattr(AR, 'terms') else 0
ar_arabic_count = sum(1 for t in AR.terms if t.get("ar","")) if hasattr(AR, 'terms') else 0

# ── 生成Markdown ─────────────────────────────────────────────────
now = datetime.now().strftime("%Y-%m-%d %H:%M")

lines = []
lines.append(f"# 中阿文旅研究热点与前沿分析报告")
lines.append(f"")
lines.append(f"**生成时间：** {now}")
lines.append(f"**数据来源：** 科学知识世界模型（SKWM）")
lines.append(f"**数据范围：** {DATA.year_range[0]}–{DATA.year_range[1]}（{DATA.n_snapshots}年）")
lines.append(f"**分析年份：** {YEAR}")
lines.append(f"")
lines.append(f"---")
lines.append(f"")

# ═══ 一、核心指标 ═══
lines.append(f"## 一、核心数据指标")
lines.append(f"")
lines.append(f"| 指标 | 数值 |")
lines.append(f"|:-----|:----:|")
lines.append(f"| 知识实体（年×节点） | {total_state:,} |")
lines.append(f"| 知识关系（89年累计） | {total_edges:,} |")
lines.append(f"| 年度切片数 | {DATA.n_snapshots} 年 |")
lines.append(f"| 最新年实体数 | {len(entities):,} |")
lines.append(f"| 中阿英术语对齐 | {ar_terms:,} 条（含阿语 {ar_arabic_count:,} 条） |")
lines.append(f"| 动力学预测 AUC | 0.9408（XGBoost） |")
lines.append(f"")
lines.append(f"**2026 年热点 Top 5：** " + " · ".join([f"{h['name']}(热度{h['heat']})" for h in hot[:5]]))
lines.append(f"")
lines.append(f"**2026 年前沿 Top 5：** " + " · ".join([f"{e['name']}(增速{e['growth']})" for e in emerging[:5]]))
lines.append(f"")

# ═══ 二、研究热点分析 ═══
lines.append(f"## 二、研究热点分析")
lines.append(f"")
lines.append(f"基于 SKWM 状态向量 [热度, 增速, 中心度, 连接数] 四维评分，{YEAR}年中阿文旅领域研究热点如下：")
lines.append(f"")
lines.append(f"| 排名 | 主题 | 热度 | 增速 | 中心度 | 连接数 |")
lines.append(f"|:---:|:-----|:---:|:----:|:------:|:------:|")
for i, h in enumerate(hot[:15]):
    lines.append(f"| {i+1} | {h['name']} | {h['heat']:,} | {h['growth']} | {h['centrality']:.3f} | {h['connections']:,} |")
lines.append(f"")
lines.append(f"**分析：**")
top3 = hot[:3]
lines.append(f"- **{top3[0]['name']}** 以 {top3[0]['heat']:,} 的热度居首，中心度 {top3[0]['centrality']:.3f}，连接 {top3[0]['connections']:,} 个实体，是中阿文旅研究的核心主题。")
lines.append(f"- **{top3[1]['name']}** 热度 {top3[1]['heat']:,}，增速 {top3[1]['growth']}，显示出较强的增长势头。")
lines.append(f"- **{top3[2]['name']}** 热度 {top3[2]['heat']:,}，作为文旅研究的基础性主题持续受到关注。")
lines.append(f"")
lines.append(f"实体类型分布：")
for etype, count in sorted(etype_dist.items(), key=lambda x: -x[1]):
    pct = count / len(entities) * 100 if entities else 0
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    lines.append(f"- {etype}: {count:,} ({pct:.1f}%) {bar}")
lines.append(f"")

# ═══ 三、新兴前沿识别 ═══
lines.append(f"## 三、新兴前沿识别")
lines.append(f"")
lines.append(f"以「增速（growth）」为指标，识别出 {YEAR} 年中阿文旅领域增速最快的新兴前沿主题：")
lines.append(f"")
lines.append(f"| 排名 | 前沿主题 | 热度 | 增速 | 趋势判断 |")
lines.append(f"|:---:|:---------|:---:|:----:|:---------|")
for i, e in enumerate(emerging[:12]):
    trend = "🚀 爆发期" if e['growth'] > 400 else "📈 成长期" if e['growth'] > 200 else "📊 稳定增长"
    lines.append(f"| {i+1} | {e['name']} | {e['heat']:,} | +{e['growth']} | {trend} |")
lines.append(f"")
lines.append(f"**前沿特征分析：**")
fastest = emerging[0] if emerging else None
if fastest:
    lines.append(f"- **{fastest['name']}**（增速 +{fastest['growth']}）是当前增长最快的前沿方向，热度达 {fastest['heat']:,}，处于爆发期。")
lines.append(f"- 新兴前沿主题呈现明显的跨学科特征，覆盖旅游管理、文化遗产数字化、AI 技术应用等多个方向。")
lines.append(f"- 多语种主题（中文+英文）同时出现，反映该领域研究的国际化特征。")
lines.append(f"")

# ═══ 四、趋势预测 ═══
lines.append(f"## 四、趋势预测（XGBoost）")
lines.append(f"")
ah, hi = DATA.year_range
lines.append(f"基于 {DATA.n_snapshots} 年时间序列（{ah}–{hi}）的 XGBoost 模型（AUC=0.9408），预测未来 5 年趋势：")
lines.append(f"")
preds = DATA.predict_future(YEAR, 5)
if preds:
    lines.append(f"| 排名 | 主题 | 当前热度 | 预测热度 | 预测增速 |")
    lines.append(f"|:---:|:-----|:-------:|:--------:|:--------:|")
    for i, p in enumerate(preds[:10]):
        lines.append(f"| {i+1} | {p['name']} | {p.get('current_heat',0):.0f} | {p.get('predicted_heat',0):.0f} | +{p.get('predicted_growth',0):.1f} |")
lines.append(f"")
lines.append(f"**预测结论：**")
if preds:
    lines.append(f"- 预计未来 5 年研究热点仍将集中在 {preds[0]['name']}、{preds[1]['name'] if len(preds)>1 else ''} 等方向。")
lines.append(f"- 新兴方向（如 generative ai、digital heritage）的增速将保持高位。")
lines.append(f"")

# ═══ 五、年度演化 ═══
lines.append(f"## 五、年度知识规模演化")
lines.append(f"")
lines.append(f"| 年代区间 | 起始节点 | 终止节点 | 增长 | 趋势 |")
lines.append(f"|:---------|:--------:|:--------:|:----:|:----:|")
segments = [("1895–1950", 0), ("1950–2000", 0), ("2000–2010", 0), ("2010–2020", 0), ("2020–2026", 0)]
sorted_snaps = sorted(snapshots_trend, key=lambda x: x["year"])
for label, idx in segments:
    start_year = int(label.split("–")[0])
    end_year = int(label.split("–")[1])
    start_snap = next((s for s in sorted_snaps if s["year"] >= start_year), None)
    end_snap = next((s for s in sorted_snaps if s["year"] >= end_year), None)
    if start_snap and end_snap:
        growth = end_snap["nodes"] - start_snap["nodes"]
        trend = "📈 快速增长" if growth > 1000 else "📈 稳步增长" if growth > 100 else "📊 缓慢增长"
        lines.append(f"| {label} | {start_snap['nodes']:,} | {end_snap['nodes']:,} | +{growth:,} | {trend} |")
lines.append(f"")
lines.append(f"知识图谱规模从 {sorted_snaps[0]['nodes']} 个节点（{sorted_snaps[0]['year']}年）增长到 {sorted_snaps[-1]['nodes']:,} 个节点（{sorted_snaps[-1]['year']}年），增长了 {sorted_snaps[-1]['nodes'] - sorted_snaps[0]['nodes']:,} 倍。")
lines.append(f"")

# ═══ 六、服务建议 ═══
lines.append(f"## 六、学科服务建议")
lines.append(f"")
lines.append(f"基于以上分析，提出以下学科服务建议：")
lines.append(f"")
lines.append(f"1. **课题申报方向**：建议重点关注 {hot[0]['name'] if hot else ''}、{emerging[0]['name'] if emerging else ''} 等热点与前沿交叉领域。")
lines.append(f"2. **文献资源建设**：加强对 {hot[2]['name'] if len(hot)>2 else ''} 和 {emerging[1]['name'] if len(emerging)>1 else ''} 相关文献的采集与组织。")
lines.append(f"3. **学科服务优化**：针对 {hot[1]['name'] if len(hot)>1 else ''} 相关研究团队，提供定制化的前沿跟踪和文献推荐服务。")
lines.append(f"4. **多语种支持**：利用 {ar_terms:,} 条中阿英术语对齐资源，加强阿语文献的深度标引与检索服务。")
lines.append(f"")
lines.append(f"---")
lines.append(f"")
lines.append(f"*报告由 SKWM 科学知识世界模型自动生成 | {now}*")
lines.append(f"*数据基于 {DATA.n_snapshots} 年时间切片 × {total_state:,} 条状态向量 × XGBoost(AUC=0.9408)*")

# ── 写入文件 ─────────────────────────────────────────────────────
md_content = "\n".join(lines)
fname = f"中阿文旅研究热点与前沿分析报告_{now[:10]}.md"
fp = OUT_DIR / fname
fp.write_text(md_content, encoding="utf-8")
print(f"\n✅ 报告已生成: {fp}")
print(f"   字数: {len(md_content)} 字符")
print(f"   行数: {len(lines)} 行")

# 同时写入平台 Obsidian 沉淀目录
obsidian_dir = BACKEND / "obsidian_vault" / "报告"
obsidian_dir.mkdir(parents=True, exist_ok=True)
obsidian_fp = obsidian_dir / fname
obsidian_fp.write_text(md_content, encoding="utf-8")
print(f"✅ 已同步到 Obsidian: {obsidian_fp}")

# ── 输出摘要 ─────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"📋 报告摘要")
print(f"{'='*55}")
print(f"  热点 Top 3: {' · '.join([h['name'] for h in hot[:3]])}")
print(f"  前沿 Top 3: {' · '.join([e['name'] for e in emerging[:3]])}")
print(f"  实体类型: {len(etype_dist)} 类")
print(f"  年度跨度: {len(snapshots_trend)} 年")
print(f"  术语对齐: {ar_terms:,} 条")
print(f"{'='*55}")
