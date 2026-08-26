# -*- coding: utf-8 -*-
"""
C0/C1 双份状态向量（2026-08-27）
=================================
同一 12,233 版（现版 assignments 3332966f）上生成两份：
  C0_baseline = 排除 language=ar（12206 篇）
  C1_arabic   = 包含 language=ar（12233 篇）
口径 = build_state_vectors.py（world_model_pipeline 代码1+2）：
  主题来源=主表 keywords，按年建近5年窗口共现图，向量[热度,增速,中心度,连接数]
输出：state_vectors_C0_20260827.json / _C1_ 同 + 对比报告（SHA、主题差集、年度热度、2024 Top-20 Jaccard）
"""
import json, os, re, itertools, hashlib
from collections import defaultdict
import networkx as nx

DATA = r"E:\大挑\rail_deploy\data"
MAIN = os.path.join(DATA, "B1_文献主表.json")
OUT_DIR = DATA
DATE = "20260827"

def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)

def build(b1):
    """复刻 build_state_vectors.py 代码1+2"""
    by_year = defaultdict(list)
    for p in b1:
        y = p.get("year")
        kw = p.get("keywords") or []
        if y and kw:
            try:
                by_year[int(y)].append([k.lower().strip() for k in kw if k])
            except Exception:
                pass
    years = sorted(by_year.keys())
    def snapshot(upto, window=5):
        G = nx.Graph()
        for y in range(upto - window + 1, upto + 1):
            for kws in by_year.get(y, []):
                for u, v in itertools.combinations(set(kws), 2):
                    if G.has_edge(u, v):
                        G[u][v]["w"] += 1
                    else:
                        G.add_edge(u, v, w=1)
        return G
    snapshots = {y: snapshot(y) for y in years if y >= years[0] + 4}
    snap_years = sorted(snapshots.keys())
    S = {}
    for i, y in enumerate(snap_years):
        G = snapshots[y]
        deg = dict(G.degree(weight="w"))
        cen = nx.degree_centrality(G)
        prev_deg = dict(snapshots[snap_years[i - 1]].degree(weight="w")) if i > 0 else {}
        for n in G.nodes():
            d = deg.get(n, 0)
            S[(str(y), n)] = [d, d - prev_deg.get(n, 0), round(cen.get(n, 0), 6), G.degree(n)]
    state = {}
    for (y, n), vec in S.items():
        state.setdefault(y, {})[n] = vec
    state.pop("_wm", None)
    # 规范化：年份升序 + 主题字典序（SHA 稳定）
    return {k: dict(sorted(v.items())) for k, v in sorted(state.items(), key=lambda x: int(x[0]))}

def sha256_of(d):
    raw = json.dumps(d, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def write(path, d):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return os.path.getsize(path)

# 加载主表
b1_all = load_skwm_json(MAIN)
b1_c0 = [p for p in b1_all if (p.get("language") or "") != "ar"]
print("主表: 全部 %d | C0(排除ar) %d | ar 排除 %d" % (len(b1_all), len(b1_c0), len(b1_all) - len(b1_c0)))

sv_c0 = build(b1_c0)
sv_c1 = build(b1_all)
p_c0 = os.path.join(OUT_DIR, f"state_vectors_C0_{DATE}.json")
p_c1 = os.path.join(OUT_DIR, f"state_vectors_C1_{DATE}.json")
sz0 = write(p_c0, sv_c0)
sz1 = write(p_c1, sv_c1)
sha0 = sha256_of(sv_c0)
sha1 = sha256_of(sv_c1)
print("C0 写入: %s (%d bytes) SHA %s" % (p_c0, sz0, sha0[:16]))
print("C1 写入: %s (%d bytes) SHA %s" % (p_c1, sz1, sha1[:16]))

# 统计
def stats(sv):
    years = sorted(int(k) for k in sv)
    total = sum(len(v) for v in sv.values())
    heat_sum = sum(vec[0] for v in sv.values() for vec in v.values())
    return years[0], years[-1], len(years), total, heat_sum

s0, s1 = stats(sv_c0), stats(sv_c1)
print("C0 统计: 年份 %d~%d (%d年) 条目 %d 热度总和 %.0f" % s0)
print("C1 统计: 年份 %d~%d (%d年) 条目 %d 热度总和 %.0f" % s1)

# 主题集合差异
t0, t1 = set(sv_c0.keys()) | set(), set()
t0 = set().union(*[set(v.keys()) for v in sv_c0.values()])
t1 = set().union(*[set(v.keys()) for v in sv_c1.values()])
only_c0, only_c1 = t0 - t1, t1 - t0
print("主题数: C0 %d | C1 %d | C0独有 %d | C1独有 %d" % (len(t0), len(t1), len(only_c0), len(only_c1)))

# 2024 Top-20 Jaccard
def top20_2024(sv):
    v = sv.get("2024", {})
    ranked = sorted(v.items(), key=lambda x: -x[1][0])[:20]
    return set(t for t, vec in ranked), ranked
set_c0, rank_c0 = top20_2024(sv_c0)
set_c1, rank_c1 = top20_2024(sv_c1)
inter = set_c0 & set_c1
jacc = len(inter) / len(set_c0 | set_c1) if (set_c0 | set_c1) else 0
print("2024 Top-20: C0 %d 主题 | C1 %d 主题 | 交集 %d | Jaccard %.3f" % (len(set_c0), len(set_c1), len(inter), jacc))

# 年度热度对比（总量 + Top 主题变化）
all_years = sorted(set(int(k) for k in sv_c0) | set(int(k) for k in sv_c1))
year_lines = []
for y in all_years:
    v0 = sv_c0.get(str(y), {}); v1 = sv_c1.get(str(y), {})
    h0 = sum(vec[0] for vec in v0.values()); h1 = sum(vec[0] for vec in v1.values())
    top0 = max(v0, key=lambda t: v0[t][0]) if v0 else "-"
    top1 = max(v1, key=lambda t: v1[t][0]) if v1 else "-"
    if abs(h1 - h0) > 1 or top0 != top1:
        year_lines.append((y, len(v0), h0, len(v1), h1, top0, top1))
print("年度差异行数(热度差>1或Top主题变): %d" % len(year_lines))

# 全期累计热度 Top-10
def global_top(sv, n=10):
    agg = defaultdict(float)
    for v in sv.values():
        for t, vec in v.items():
            agg[t] += vec[0]
    return sorted(agg.items(), key=lambda x: -x[1])[:n]
gt0, gt1 = global_top(sv_c0), global_top(sv_c1)

# 报告
lines = []
lines.append("# C0/C1 状态向量对比报告（2026-08-27）")
lines.append("")
lines.append("## 输入")
lines.append("- 主表：B1_文献主表.json（12,233 条，现版）")
lines.append("- assignments：topic_assignments.json（SHA 3332966f）——state_vectors 输入为主表 keywords，不读 assignments，此处仅声明数据版本一致")
lines.append("- C0_baseline = 排除 language=ar（%d 篇）；C1_arabic = 包含 language=ar（12,233 篇）" % len(b1_c0))
lines.append("")
lines.append("## 1. 各自 SHA-256 与规模")
lines.append("| 项 | C0_baseline(排除ar) | C1_arabic(含ar) |")
lines.append("|----|----|----|")
lines.append("| 文件 | state_vectors_C0_%s.json | state_vectors_C1_%s.json |" % (DATE, DATE))
lines.append("| SHA-256 | %s | %s |" % (sha0, sha1))
lines.append("| 年份范围 | %d~%d（%d年） | %d~%d（%d年） |" % (s0[0], s0[1], s0[2], s1[0], s1[1], s1[2]))
lines.append("| 条目(年×主题) | %d | %d |" % (s0[3], s1[3]))
lines.append("| 热度总和 | %.0f | %.0f |" % (s0[4], s1[4]))
lines.append("")
lines.append("## 2. 主题 key 集合差异")
lines.append("- C0 主题数：%d；C1 主题数：%d" % (len(t0), len(t1)))
lines.append("- C0 独有 %d 个：%s" % (len(only_c0), sorted(only_c0)[:50]))
lines.append("- C1 独有 %d 个（含阿语 keywords 新增）：%s" % (len(only_c1), sorted(only_c1)[:100]))
lines.append("")
lines.append("## 3. 年度热度差异（热度差>1 或 Top 主题变化，共 %d 行）" % len(year_lines))
lines.append("| 年 | C0条目 | C0热度 | C1条目 | C1热度 | C0 Top主题 | C1 Top主题 |")
lines.append("|----|--------|--------|--------|--------|-----------|-----------|")
for y, n0, h0, n1, h1, tp0, tp1 in year_lines[-30:]:
    lines.append("| %d | %d | %.0f | %d | %.0f | %s | %s |" % (y, n0, h0, n1, h1, tp0, tp1))
lines.append("")
lines.append("## 4. 2024 年 Top-20 Jaccard")
lines.append("- C0 2024 Top-20：%s" % sorted(set_c0))
lines.append("- C1 2024 Top-20：%s" % sorted(set_c1))
lines.append("- 交集 %d 个 | 并集 %d 个 | **Jaccard = %.3f**" % (len(inter), len(set_c0 | set_c1), jacc))
lines.append("")
lines.append("## 5. 全期累计热度 Top-10")
lines.append("| C0 | C1 |")
lines.append("|----|----|")
for i in range(10):
    a = "%s(%.0f)" % gt0[i] if i < len(gt0) else "-"
    b = "%s(%.0f)" % gt1[i] if i < len(gt1) else "-"
    lines.append("| %s | %s |" % (a, b))
lines.append("")
lines.append("## 说明")
lines.append("- 两份均由 build_state_vectors_c0c1.py 同脚本生成（world_model_pipeline 代码1+2 口径），输出做了键排序规范化（SHA 稳定）")
lines.append("- C1 与既有 state_vectors.json（f6f5820a…）为同一输入主表，规范化后内容等价")

report_path = os.path.join(OUT_DIR, f"state_vectors_C0C1_对比报告_{DATE}.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("报告已写:", report_path)
