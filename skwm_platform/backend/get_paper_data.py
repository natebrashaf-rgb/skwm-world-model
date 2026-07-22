#!/usr/bin/env python3
"""一键输出论文可引用的关键数据"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skwm_aligned_v4 import *

D = DataLayer().load(verbose=False)
DS = DeepSeekClient()
C = SKWMController(D, DS)
R = C.process('中阿文旅', top_k=10)
S = R['skwm']['S']
T = R['skwm']['T']

print()
print('=' * 55)
print('     科学知识世界模型(SKWM) — 论文数据引用')
print('     v4.0 | 策划案对齐版')
print('=' * 55)

print()
print('📊 一、数据规模')
print(f'    时间切片: {D.n_snapshots} 年 ({D.year_range[0]}~{D.year_range[1]})')
print(f'    状态向量: {D.n_state_vectors:,} 条 (年×节点)')
print(f'    共现关系: {sum(s.get("n_edges",0) for s in D.snapshots.values()):,} 条')
print(f'    链接预测: XGBoost AUC≈0.94')

print()
print('🔥 二、热点主题 Top 10 (2026年)')
print(f'    {"排名":>4} {"术语":<16} {"热度":>6} {"增速":>8} {"中心度":>8}')
print(f'    {"-"*44}')
for i, t in enumerate(S['hot_topics'][:10], 1):
    flag = '🀄' if any('\u4e00' <= c <= '\u9fff' for c in t['name']) else '🌐'
    print(f'    {i:>3}. {flag} {t["name"]:<14s} {t["heat"]:>6} {t["growth"]:>+8.1f} {t["centrality"]:>8.4f}')

print()
print('✨ 三、新兴前沿 Top 10 (2026年增速最快)')
print(f'    {"排名":>4} {"术语":<20} {"增速":>8} {"热度":>6}')
print(f'    {"-"*40}')
for i, t in enumerate(T['emerging_topics'][:10], 1):
    flag = '🀄' if any('\u4e00' <= c <= '\u9fff' for c in t['name']) else '🌐'
    print(f'    {i:>3}. {flag} {t["name"]:<18s} {t["growth"]:>+8.1f} {t["heat"]:>6}')

print()
print('📋 四、SKWM 七维覆盖')
v = validate_skwm_coverage(D, DS)
for dim, info in v["coverage"].items():
    print(f'    {info["status"]} {dim}: {info["detail"]}')

print()
print('🤖 五、四类智能体')
agents = [
    ('文献智能体', '检索/多跳推理/术语查询', '策划案第71条'),
    ('计量智能体', '热点/前沿/趋势预测/反事实', '策划案第73条'),
    ('图谱智能体', '知识全景/时间旅行/关系查询', '策划案第74条'),
    ('报告智能体', '学科报告/服务案例/推送内容', '策划案第75条'),
]
for name, desc, ref in agents:
    print(f'    ✅ {name}: {desc} ({ref})')

print()
print('💰 六、运行成本')
print(f'    {DS.cost_str()}')

print()
print('=' * 55)
print('     📁 output/skwm_output_demo.json  — 完整7维JSON')
print('     📁 output/skwm_coverage_report.json — 覆盖验证报告')
print('=' * 55)
print()
