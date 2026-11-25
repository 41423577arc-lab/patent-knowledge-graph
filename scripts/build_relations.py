"""P1-4: build citations and cooperation from cleaned relations.

Citations use only sample patents as the citing side (backward citations from
`引证专利`), so `citing_id` is always in patents.parquet. Cited IDs are mapped
to representative public numbers by stripping the kind code. External applicant
is filled only when the source row identifies exactly one applicant.
"""
import argparse
import json
import re
import shutil
import time
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd

from core import config

REPS_FULL = config.RESULTS_DIR / "representatives.parquet"
REPS_SAMPLE = config.RESULTS_DIR / "_tech_sample" / "representatives.parquet"
PATENTS_FULL = config.PROCESSED_DIR / "patents.parquet"
PATENTS_SAMPLE = config.RESULTS_DIR / "_clean_sample" / "patents.parquet"
APPLICANTS_FULL = config.PROCESSED_DIR / "applicants.parquet"
APPLICANTS_SAMPLE = config.RESULTS_DIR / "_clean_sample" / "applicants.parquet"
OUT_FULL = config.PROCESSED_DIR
OUT_SAMPLE = config.RESULTS_DIR / "_relations_sample"
DELIVERY_DIR = config.ROOT_DIR / "交付给同伴的内容" / "P1-4_引用合作"

KIND_RE = re.compile(r"[A-Z]\d*$")
NUM_RE = re.compile(r"\d")


def s(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def split_multi(v) -> list[str]:
    return [x.strip() for x in re.split(r"[;；|]", s(v)) if x.strip()]


def strip_kind(pid: str) -> str:
    return KIND_RE.sub("", pid.upper().replace(" ", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    reps_path = REPS_SAMPLE if args.sample else REPS_FULL
    patents_path = PATENTS_SAMPLE if args.sample else PATENTS_FULL
    applicants_path = APPLICANTS_SAMPLE if args.sample else APPLICANTS_FULL
    for p in (reps_path, patents_path, applicants_path):
        if not p.is_file():
            raise SystemExit(f"missing input: {p}")

    patents = pd.read_parquet(patents_path)
    applicants = pd.read_parquet(applicants_path)
    reps = pd.read_parquet(reps_path)

    pid_set = set(patents["patent_id"].astype(str))
    rep_base = {}
    base_collisions = 0
    for pid in pid_set:
        base = strip_kind(pid)
        if base in rep_base and rep_base[base] != pid:
            base_collisions += 1
        else:
            rep_base[base] = pid

    # In-sample cited applicant: only when the cited patent has one standardized applicant.
    app_by_patent = defaultdict(set)
    for pid, name in zip(applicants["patent_id"], applicants["applicant_std"]):
        if pd.notna(name) and s(name):
            app_by_patent[str(pid)].add(s(name))
    single_applicant = {pid: next(iter(names)) for pid, names in app_by_patent.items()
                        if len(names) == 1}

    # First pass: map an external cited token to applicant names where the source
    # row can be aligned (one cited patent, or equal-length lists).
    token_apps = defaultdict(set)
    for rec in reps.itertuples(index=False):
        cites = s(rec.cites)
        if not cites:
            continue
        tokens = []
        seen = set()
        for t in split_multi(cites):
            t = t.upper().replace(" ", "")
            if t and t not in seen:
                seen.add(t)
                tokens.append(t)
        apps = split_multi(rec.cited_applicants)
        if not apps:
            continue
        if len(tokens) == 1:
            for a in apps:
                token_apps[tokens[0]].add(a)
        elif len(apps) == len(tokens):
            for t, a in zip(tokens, apps):
                if a:
                    token_apps[t].add(a)

    edges = {}
    external_rows = set()
    rows_with_cites = 0
    raw_tokens = 0
    invalid_tokens = 0
    self_edges = 0
    citing_with_edges = set()

    for rec in reps.itertuples(index=False):
        citing = s(rec.patent_id)
        cites = s(rec.cites)
        if not citing or not cites:
            continue
        rows_with_cites += 1
        tokens = []
        seen_tokens = set()
        for t in split_multi(cites):
            t = t.upper().replace(" ", "")
            if not t:
                continue
            raw_tokens += 1
            if len(t) < 5 or not NUM_RE.search(t):
                invalid_tokens += 1
                continue
            if t in seen_tokens:
                continue
            seen_tokens.add(t)
            tokens.append(t)

        for t in tokens:
            base = strip_kind(t)
            rep = rep_base.get(base)
            if rep:
                cited = rep
                in_sample = True
                cited_app = single_applicant.get(cited)
            else:
                cited = t
                in_sample = False
                apps = token_apps.get(t, set())
                cited_app = next(iter(apps)) if len(apps) == 1 else None
                for a in apps:
                    external_rows.add((citing, cited, a))

            if citing == cited:
                self_edges += 1
                continue
            key = (citing, cited)
            if key in edges:
                continue
            edges[key] = (in_sample, cited_app)
            citing_with_edges.add(citing)

    citations = pd.DataFrame(
        [(c, d, ins, app) for (c, d), (ins, app) in edges.items()],
        columns=["citing_id", "cited_id", "cited_in_sample", "cited_applicant_std"],
    )
    for col in ["citing_id", "cited_id", "cited_applicant_std"]:
        citations[col] = citations[col].astype("string")
    citations["cited_in_sample"] = citations["cited_in_sample"].astype("boolean")

    external_df = pd.DataFrame(
        sorted(external_rows),
        columns=["citing_id", "cited_id", "applicant"],
    )
    for col in ["citing_id", "cited_id", "applicant"]:
        external_df[col] = external_df[col].astype("string")
    external_edges_with_app = len({(c, d) for c, d, _ in external_rows})

    # Cooperation: each patent contributes one pair per distinct applicant pair.
    pair_counter = Counter()
    multi_patents = 0
    for pid, group in applicants.groupby("patent_id", sort=False):
        names = sorted({s(x) for x in group["applicant_std"] if s(x)})
        if len(names) < 2:
            continue
        multi_patents += 1
        for a, b in combinations(names, 2):
            pair_counter[(a, b)] += 1

    cooperation = pd.DataFrame(
        [(a, b, w) for (a, b), w in pair_counter.items()],
        columns=["app_a", "app_b", "weight"],
    )
    cooperation["app_a"] = cooperation["app_a"].astype("string")
    cooperation["app_b"] = cooperation["app_b"].astype("string")
    cooperation["weight"] = cooperation["weight"].astype("int64")

    in_sample_edges = int(citations["cited_in_sample"].fillna(False).sum())
    total_edges = len(citations)
    with_applicant = int(citations["cited_applicant_std"].notna().sum())
    top_pairs = pair_counter.most_common(15)

    counts = {
        "source_reps": str(reps_path),
        "sample_mode": args.sample,
        "patents": len(patents),
        "representatives": len(reps),
        "citations": {
            "rows_with_cites": rows_with_cites,
            "raw_cited_tokens": raw_tokens,
            "invalid_tokens": invalid_tokens,
            "self_edges_skipped": self_edges,
            "unique_edges": total_edges,
            "in_sample_edges": in_sample_edges,
            "external_edges": total_edges - in_sample_edges,
            "in_sample_rate": round(in_sample_edges / total_edges, 4) if total_edges else None,
            "edges_with_applicant": with_applicant,
            "applicant_coverage": round(with_applicant / total_edges, 4) if total_edges else None,
            "external_edges_with_applicant": external_edges_with_app,
            "external_applicant_coverage": round(
                external_edges_with_app / max(total_edges - in_sample_edges, 1), 4
            ),
            "external_applicant_rows": len(external_df),
            "tokens_with_multiple_applicants": sum(
                1 for v in token_apps.values() if len(v) > 1
            ),
            "citing_patents_with_edges": len(citing_with_edges),
            "base_collisions": base_collisions,
            "rows_with_cited_by": int(reps["cited_by"].notna().sum()) if "cited_by" in reps else None,
        },
        "cooperation": {
            "multi_applicant_patents": multi_patents,
            "pairs": len(cooperation),
            "max_weight": int(cooperation["weight"].max()) if len(cooperation) else 0,
            "top_pairs": [{"app_a": a, "app_b": b, "weight": w} for (a, b), w in top_pairs],
        },
        "elapsed_sec": round(time.time() - t0, 1),
    }

    if args.sample:
        out_dir = OUT_SAMPLE
        counts_path = config.RESULTS_DIR / "relation_counts_sample.json"
    else:
        out_dir = OUT_FULL
        counts_path = config.RESULTS_DIR / "relation_counts.json"

    out_dir.mkdir(parents=True, exist_ok=True)
    external_path = (OUT_SAMPLE if args.sample else config.RESULTS_DIR) / "external_citation_applicants.parquet"
    external_path.parent.mkdir(parents=True, exist_ok=True)
    external_df.to_parquet(external_path, index=False)
    counts["external_applicants_path"] = str(external_path)
    citations.to_parquet(out_dir / "citations.parquet", index=False)
    cooperation.to_parquet(out_dir / "cooperation.parquet", index=False)
    counts_path.write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.sample:
        DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("citations.parquet", "cooperation.parquet"):
            shutil.copy2(out_dir / name, DELIVERY_DIR / name)
        shutil.copy2(external_path, DELIVERY_DIR / "external_citation_applicants.parquet")
        shutil.copy2(counts_path, DELIVERY_DIR / "relation_counts.json")
        top_lines = "\n".join(
            f"| {a} ↔ {b} | {w} |" for (a, b), w in top_pairs[:10]
        )
        readme = f"""# P1-4 引用与合作

生成时间：{datetime.now().isoformat(timespec='seconds')}
输入：`representatives.parquet`、`applicants.parquet`、`patents.parquet`

## 文件

| 文件 | 行 × 列 | 说明 |
|---|---|---|
| `citations.parquet` | {len(citations):,} × 4 | 专利引用边，`citing_id → cited_id` |
| `external_citation_applicants.parquet` | {len(external_df):,} × 3 | 外部引用主体明细，供 P3 依赖分析（非契约 C） |
| `cooperation.parquet` | {len(cooperation):,} × 3 | 共同申请边，`weight` 为去重专利数 |
| `relation_counts.json` | — | 覆盖率与 Top 合作对 |

## 引用口径

- 只从**样本内专利**的 `引证专利` 建边：`citing_id` 一定是样本内专利。
- `cited_id` 先用 kind code 归一（如 `CN109901271A` 与 `B` 视为同一件），能映射到样本内代表专利就标 `cited_in_sample=True`，否则保留原公开号、标 `false`。
- 外部被引主体先从“单件引用/等长列表”可对齐的行建立映射，再用于其他边；标量 `cited_applicant_std` 只在该外部专利唯一主体时填写，否则留空，明细见辅助表。
- `被引证专利`（正向引用）不建边，避免引入大量样本外 `citing_id`；它仍保留在 `representatives.parquet` 供统计。
- 自引边跳过。

## 外部引用主体辅助表

- `external_citation_applicants.parquet` **不是契约 C 的七张表之一**，仅供 P3 构建企业级依赖/风险边。
- 来源：`被引证专利` 与 `被引证申请人` 能按“单件引用”或等长列表对齐的部分。
- 一个外部专利可能对应多个申请人，所以它是明细表，不是标量；`citations.cited_applicant_std` 只在该外部专利唯一主体时填写。
- 有 {counts['citations']['tokens_with_multiple_applicants']:,} 个外部专利对应多个申请人，这些在标量字段留空，明细表保留。

## 合作口径

- 同一专利的 `applicant_std` 去重后两两配对；
- 每对只存一条边，`app_a < app_b`，`weight` = 共同申请的去重专利数。

## 关键计数

- 引用边：{total_edges:,}；样本内 {in_sample_edges:,}（{counts['citations']['in_sample_rate']*100:.1f}%），外部 {total_edges-in_sample_edges:,}
- 有引用边的样本专利：{len(citing_with_edges):,}
- 有被引申请人的边：{with_applicant:,}（{counts['citations']['applicant_coverage']*100:.1f}%）
- 外部引用有主体的边：{external_edges_with_app:,}（{counts['citations']['external_applicant_coverage']*100:.1f}%）；明细 {len(external_df):,} 行
- 多申请人专利：{multi_patents:,}；合作边：{len(cooperation):,}；最大权重：{counts['cooperation']['max_weight']}

## Top 合作对

| 主体对 | 共同专利数 |
|---|---:|
{top_lines}

## 局限

- 样本内引用边只占 {counts['citations']['in_sample_rate']*100:.1f}%，专利级引用网络稀疏；企业级依赖分析应结合辅助表。
- 外部主体映射覆盖 {counts['citations']['external_applicant_coverage']*100:.1f}%，多数外部边仍无主体；依赖分析会受此限制。
- kind code 归一后有 {base_collisions} 组 base 冲突，按首个代表专利映射，少量边可能误连。
- 合作网络只基于标准化申请人；同一集团不同子公司若未归并，会表现为不同节点。

## P1-8 补充：企业级引用聚合（口径 C）

- `data/results/company_citation_pairs.parquet` 是从 `representatives.cited_applicants` 聚合出的**主体级**辅助表：`citing_company, cited_company, citing_patent_count`，共 135,007 对、165,355 条专利-主体对计数。
- 同一件引用专利对同一被引主体只计一次；它是“引用集合里出现过”的聚合，不是精确的专利级边。
- 需要精确外部边时，用 `external_citation_applicants.parquet` 的 `(citing_id, cited_id, applicant)` 明细；需要快速展示时用 `company_citation_pairs.parquet`。
- 企业名通过 `company_alias.csv` 归一；Kia 与 Hyundai 不合并，`中国南方` 标 `pending_review`。
"""
        (DELIVERY_DIR / "说明.md").write_text(readme, encoding="utf-8")

    print("written", out_dir / "citations.parquet", out_dir / "cooperation.parquet", counts_path)
    print(json.dumps(counts, ensure_ascii=True, indent=2))
    print("elapsed", counts["elapsed_sec"])


if __name__ == "__main__":
    main()
