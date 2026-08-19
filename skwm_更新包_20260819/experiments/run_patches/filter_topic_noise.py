# -*- coding: utf-8 -*-
"""
filter_topic_noise.py — state_vectors 主题噪声过滤 (v1)
======================================================
背景:
  data_profile_report.md 自述 state_vectors 含大量通用学术英文词
  (gene/rate/search/black/...),盲评输出中 'gene'(growth=638 全库最高)、
  'genomics'、'in the united states' 等垃圾主题污染预测榜。

本脚本:
  1. 读 data/state_vectors.json
  2. 按停用词表 + 垃圾短语表过滤每个年份的主题
  3. 输出:
       data/state_vectors_clean.json   (清洗后,同 schema)
       output/topic_noise_filter_record.json (删除记录 + 统计)
  4. 若 --replace,用清洗版覆盖 data/state_vectors.json(原文件备份为
     data/state_vectors_raw.json.bak)

用法:
    python filter_topic_noise.py            # 只生成 _clean + 记录
    python filter_topic_noise.py --replace  # 覆盖 data/state_vectors.json
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "topic_noise_filter"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 停用词表
# ============================================================
# 1) 团队 data_profile_report.md 自认的通用学术噪声词(原样收录)
ACADEMIC_STOP = """
burden gene rate search access change case cell report analysis data
development effect evaluation expression group health impact level
management method model network performance process research response
result review risk role score state status study system technology
test treatment use value
""".split()

# 2) 盲评输出中实际出现的垃圾主题(中阿文旅场景下无意义)
JUNK_TOPICS = """
black genomics multidisciplinary evolution guidelines opportunities
challenges introduction findings objective objectives aim aims purpose
conclusion outcomes approach approaches factor factors determinant
determinants variable variables correlation association predictor
predictors baseline cohort sample samples participant participants
view views abbreviations methodology instruction land power appendix whose references acknowledgements results
""".split()

# 3) 垃圾短语(带空格的主题名)
JUNK_PHRASES = [
    "in the united states", "the united states", "in the united",
    "united states", "opportunities and challenges", "guidelines for the",
    "an introduction", "as an", "of an", "in chinese", "a new",
    "the role of", "the impact of", "a study of", "a review of",
    "introduction to",
]

STOP = set(w.lower() for w in ACADEMIC_STOP + JUNK_TOPICS)
PHRASES = [p.lower() for p in JUNK_PHRASES]


def is_noise(topic: str) -> bool:
    t = topic.strip().lower()
    if not t:
        return True
    if t in STOP:
        return True
    for p in PHRASES:
        if p in t:
            return True
    # 纯数字 / 单字母
    if re.fullmatch(r"[\d\W]+", t):
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true",
                        help="用清洗版覆盖 data/state_vectors.json")
    args = parser.parse_args()

    src = DATA_DIR / "state_vectors.json"
    sv = json.loads(src.read_text(encoding="utf-8"))
    years = sorted(int(k) for k in sv if k != "_wm" and isinstance(sv[k], dict))

    removed_record = {}
    total_before = total_after = 0
    removed_counter = Counter()

    clean = {}
    for y in years:
        d = sv[str(y)]
        removed = {k: v for k, v in d.items() if is_noise(k)}
        kept = {k: v for k, v in d.items() if not is_noise(k)}
        clean[str(y)] = kept
        total_before += len(d)
        total_after += len(kept)
        removed_counter.update(removed.keys())
        if removed:
            removed_record[str(y)] = removed

    # 被移除主题的去重清单(带热度和出现年数)
    removed_topics = []
    for name, cnt in removed_counter.most_common():
        # 取最近一年的向量作示例
        example = None
        for y in sorted(removed_record, key=int, reverse=True):
            if name in removed_record[y]:
                example = removed_record[y][name]
                break
        removed_topics.append({
            "topic": name,
            "years_present": cnt,
            "example_vector": example,
        })

    stats = {
        "years": years,
        "total_topic_entries_before": total_before,
        "total_topic_entries_after": total_after,
        "removed_entries": total_before - total_after,
        "unique_topics_removed": len(removed_topics),
        "unique_topics_remaining": len(set(
            t for y in years for t in clean[str(y)])),
        "top_removed": removed_topics[:30],
    }

    # 输出清洗版
    out_clean = DATA_DIR / "state_vectors_clean.json"
    out_clean.write_text(
        json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")

    record_path = OUT_DIR / "topic_noise_filter_record.json"
    record_path.write_text(
        json.dumps({"stats": stats, "removed_by_year": removed_record},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 60)
    print("  主题噪声过滤")
    print("=" * 60)
    print(f"  年份: {years[0]}-{years[-1]} ({len(years)}年)")
    print(f"  主题条目: {total_before:,} → {total_after:,} "
          f"(移除 {total_before - total_after:,}, "
          f"{100 * (total_before - total_after) / max(1, total_before):.1f}%)")
    print(f"  去重主题: 移除 {len(removed_topics)} 个, "
          f"保留 {stats['unique_topics_remaining']} 个")
    print("\n  移除最多的主题:")
    for r in removed_topics[:15]:
        print(f"    {r['topic']!r:45s} 出现{r['years_present']}年")
    print(f"\n[OK] 清洗版: {out_clean}")
    print(f"[OK] 记录:   {record_path}")

    if args.replace:
        bak = DATA_DIR / "state_vectors_raw.json.bak"
        if not bak.exists():
            bak.write_bytes(src.read_bytes())
            print(f"[备份] 原始文件: {bak}")
        src.write_bytes(out_clean.read_bytes())
        print(f"[OK] 已用清洗版覆盖 {src}")


if __name__ == "__main__":
    main()
