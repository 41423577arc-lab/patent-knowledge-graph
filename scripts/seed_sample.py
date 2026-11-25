"""Rebuild the committed development sample from the processed seven tables.

The old sample came from ``data/legacy`` and had most fields empty.  This
version takes 400 patents stratified by type / primary domain / application
year cohort, then adds up to 100 citation-closure patents so that the sample
contains in-sample CITES edges and short citation chains.

It never invents values: every row is copied from ``data/processed``.
Run ``python -m scripts.seed_sample``; then ``python -m eval.check_contracts``.
"""
import json
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd

from core.config import DATA_DIR, PROCESSED_DIR, RESULTS_DIR
from core.data_loader import TABLE_COLUMNS

SEED = 20261125
BASE_N = 400
MAX_N = 500
CLOSURE_1 = 50
CLOSURE_2 = 50
COHORT_BINS = [0, 2009, 2014, 2019, 2023, 2100]
COHORT_LABELS = ["<=2009", "2010-2014", "2015-2019", "2020-2023", "2024-2025"]
TABLE_NAMES = list(TABLE_COLUMNS)


def _allocate(total: int, sizes: pd.Series, min_each: int = 1) -> dict:
    """Integer quotas proportional to sizes, at least ``min_each`` per group.

    Groups with zero rows are dropped.  The result sums to ``total`` whenever
    ``total <= sizes.sum()``.
    """
    sizes = {str(k): int(v) for k, v in sizes.items() if int(v) > 0}
    if total <= 0 or not sizes:
        return {}
    keys = list(sizes)
    if total <= min_each * len(keys):
        top = sorted(keys, key=lambda k: sizes[k], reverse=True)[:total]
        return {k: min_each for k in top}
    denom = sum(sizes.values())
    ideal = {k: total * sizes[k] / denom for k in keys}
    quota = {k: min(sizes[k], max(min_each, int(ideal[k]))) for k in keys}
    while sum(quota.values()) > total:
        candidates = [k for k in keys if quota[k] > min_each]
        if not candidates:
            break
        key = max(candidates, key=lambda k: quota[k] - ideal[k])
        quota[key] -= 1
    while sum(quota.values()) < total:
        candidates = [k for k in keys if quota[k] < sizes[k]]
        if not candidates:
            break
        key = max(candidates, key=lambda k: ideal[k] - quota[k])
        quota[key] += 1
    return quota


def _primary_domain(topic: pd.DataFrame) -> pd.Series:
    """Pick one deterministic domain label per patent for stratification."""
    return topic.groupby("patent_id")["domain"].agg(lambda s: sorted(set(s))[0])


def _stratified_base(patents: pd.DataFrame, domain: pd.Series) -> pd.Series:
    """Return the selected patent_id values for the 400-patent base."""
    frame = patents[["patent_id", "patent_type", "apply_year"]].copy()
    frame["domain"] = frame["patent_id"].map(domain).fillna("(无主题)")
    frame["cohort"] = pd.cut(frame["apply_year"], COHORT_BINS, labels=COHORT_LABELS)
    frame["cohort"] = frame["cohort"].astype("object").fillna("(缺失)")
    frame["domain"] = frame["domain"].where(frame["patent_type"] != "外观设计", "外观设计")

    selected = []
    offsets = {}
    type_quota = _allocate(BASE_N, frame["patent_type"].value_counts())
    for type_index, (patent_type, type_n) in enumerate(sorted(type_quota.items())):
        of_type = frame[frame["patent_type"] == patent_type]
        if patent_type == "外观设计":
            cells = [("外观设计", of_type)]
        else:
            domain_quota = _allocate(type_n, of_type["domain"].value_counts())
            cells = [(dom, of_type[of_type["domain"] == dom]) for dom in sorted(domain_quota)]
        for cell_index, (cell, cell_frame) in enumerate(cells):
            cell_n = type_quota[patent_type] if patent_type == "外观设计" else domain_quota[cell]
            cohort_quota = _allocate(cell_n, cell_frame["cohort"].value_counts())
            for cohort in sorted(cohort_quota):
                n = cohort_quota[cohort]
                pick = cell_frame[cell_frame["cohort"] == cohort]
                key = (patent_type, cell, cohort)
                offsets[key] = offsets.get(key, 0) + 1
                seed = SEED + 1000 * type_index + 10 * cell_index + offsets[key]
                chosen = pick.sample(n=min(n, len(pick)), random_state=seed)["patent_id"]
                selected.append(pd.DataFrame({
                    "patent_id": chosen.to_numpy(),
                    "selection": "base_stratified",
                    "stratum": f"{patent_type}/{cell}/{cohort}",
                }))
    return pd.concat(selected, ignore_index=True)


def _citation_closure(citations: pd.DataFrame, full_ids: set, selected: set,
                      citing_ids: set, budget: int, reason: str) -> pd.DataFrame:
    """Add most frequently cited in-scope patents cited by ``citing_ids``."""
    candidates = citations[
        citations["citing_id"].isin(citing_ids)
        & citations["cited_id"].isin(full_ids)
        & ~citations["cited_id"].isin(selected)
    ].copy()
    if candidates.empty or budget <= 0:
        return pd.DataFrame(columns=["patent_id", "selection", "stratum"])
    score = (candidates.groupby("cited_id")
             .agg(n_citing=("citing_id", "nunique"), n_edges=("citing_id", "size"))
             .sort_values(["n_citing", "n_edges"], ascending=False))
    picks = score.head(budget).index.tolist()
    return pd.DataFrame({
        "patent_id": picks,
        "selection": reason,
        "stratum": [f"citation_closure/{reason}" for _ in picks],
    })


def _subset(table: pd.DataFrame, ids: set, key: str = "patent_id") -> pd.DataFrame:
    return table[table[key].isin(ids)].copy()


def _cooperation_from_applicants(applicants: pd.DataFrame) -> pd.DataFrame:
    pairs = []
    for _, group in applicants.groupby("patent_id")["applicant_std"]:
        pairs.extend(combinations(sorted(set(group.dropna().astype(str))), 2))
    if not pairs:
        return pd.DataFrame(columns=TABLE_COLUMNS["cooperation"])
    out = (pd.DataFrame(pairs, columns=["app_a", "app_b"])
           .groupby(["app_a", "app_b"]).size().reset_index(name="weight"))
    out["app_a"] = out["app_a"].astype("string")
    out["app_b"] = out["app_b"].astype("string")
    out["weight"] = out["weight"].astype("int64")
    return out.sort_values(["weight", "app_a", "app_b"], ascending=[False, True, True],
                           ignore_index=True)


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def main():
    tables = {name: pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")
              for name in TABLE_NAMES}
    patents = tables["patents"]
    full_ids = set(patents["patent_id"])

    domain = _primary_domain(tables["patent_topic"])
    base = _stratified_base(patents, domain)
    selected = set(base["patent_id"])
    trace = [base]

    closure_1 = _citation_closure(
        tables["citations"], full_ids, selected, selected, CLOSURE_1, "citation_closure_1")
    trace.append(closure_1)
    selected.update(closure_1["patent_id"])

    citation_1_ids = set(closure_1["patent_id"])
    closure_2 = _citation_closure(
        tables["citations"], full_ids, selected, citation_1_ids, CLOSURE_2, "citation_closure_2")
    trace.append(closure_2)
    selected.update(closure_2["patent_id"])

    trace = pd.concat(trace, ignore_index=True).drop_duplicates("patent_id", keep="first")
    trace = trace.sort_values(["selection", "patent_id"], ignore_index=True)
    sample_ids = set(trace["patent_id"])
    assert len(sample_ids) == len(trace) <= MAX_N, (len(sample_ids), len(trace))

    sample = {name: _subset(table, sample_ids) for name, table in tables.items()
              if name not in {"cooperation", "citations"}}
    sample["patents"]["is_in_sample"] = True

    citing = tables["citations"][tables["citations"]["citing_id"].isin(sample_ids)].copy()
    citing["cited_in_sample"] = citing["cited_id"].isin(sample_ids)
    sample["citations"] = citing

    sample["cooperation"] = _cooperation_from_applicants(sample["applicants"])
    for name in TABLE_NAMES:
        sample[name] = sample[name][TABLE_COLUMNS[name]]

    target = DATA_DIR / "_sample"
    target.mkdir(parents=True, exist_ok=True)
    for name in TABLE_NAMES:
        sample[name].to_parquet(target / f"{name}.parquet", index=False)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    selection_path = RESULTS_DIR / "sample_selection.csv"
    trace.to_csv(selection_path, index=False, encoding="utf-8-sig")

    pat = sample["patents"]
    app = sample["applicants"]
    non_design = pat[pat["patent_type"] != "外观设计"]
    multi = app.groupby("patent_id").size()
    multi = multi[multi >= 2]
    cites = sample["citations"]
    in_edges = int(cites["cited_in_sample"].sum())
    co = sample["cooperation"]
    top_co = [{"app_a": r.app_a, "app_b": r.app_b, "weight": int(r.weight)}
              for r in co.head(10).itertuples()]
    year_counts = (pat["apply_year"].dropna().astype(int).value_counts().sort_index()
                   .loc[lambda s: s.index >= 2010])

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "data/processed/*.parquet (full contract C tables)",
        "kind": "development_sample",
        "seed": SEED,
        "patents": len(pat),
        "selection": {
            "base": f"{len(base)} patents stratified by patent_type / primary topic domain / application-year cohort",
            "citation_closure_1": len(closure_1),
            "citation_closure_2": len(closure_2),
            "rule": "base 400 + up to 50 patents cited by base + up to 50 cited by the first closure",
            "trace": "data/results/sample_selection.csv",
        },
        "tables": {name: len(table) for name, table in sample.items()},
        "patents_by_type": {str(k): int(v) for k, v in pat["patent_type"].value_counts().items()},
        "patents_by_country_top": {str(k): int(v) for k, v in
                                   pat["country"].value_counts().head(15).items()},
        "patents_by_year": {str(k): int(v) for k, v in year_counts.items()},
        "primary_domain": {str(k): int(v) for k, v in
                           pat["patent_id"].map(domain).fillna("(无主题)").value_counts().items()},
        "coverage": {
            "non_design_patents": len(non_design),
            "with_ipc": int(non_design["patent_id"].isin(sample["patent_ipc"]["patent_id"]).sum()),
            "with_ipc_pct": _pct(int(non_design["patent_id"].isin(sample["patent_ipc"]["patent_id"]).sum()), len(non_design)),
            "with_topic": int(non_design["patent_id"].isin(sample["patent_topic"]["patent_id"]).sum()),
            "with_topic_pct": _pct(int(non_design["patent_id"].isin(sample["patent_topic"]["patent_id"]).sum()), len(non_design)),
            "with_efficacy": int(non_design["patent_id"].isin(sample["patent_efficacy"]["patent_id"]).sum()),
            "with_efficacy_pct": _pct(int(non_design["patent_id"].isin(sample["patent_efficacy"]["patent_id"]).sum()), len(non_design)),
        },
        "applicants": {
            "rows": len(app),
            "unique_std": int(app["applicant_std"].nunique()),
            "multi_applicant_patents": int(len(multi)),
            "missing_type_rows": int(app["applicant_type"].isna().sum()),
        },
        "citations_sample": {
            "edges": len(cites),
            "citing_patents": int(cites["citing_id"].nunique()),
            "in_sample_edges": in_edges,
            "external_edges": int(len(cites) - in_edges),
            "in_sample_pct": _pct(in_edges, len(cites)),
            "edges_with_cited_applicant": int(cites["cited_applicant_std"].notna().sum()),
        },
        "cooperation_sample": {
            "edges": len(co),
            "top": top_co,
        },
        "missing_in_sample": {
            column: int(pat[column].isna().sum()) for column in
            ["title", "abstract", "apply_date", "apply_year", "pub_date", "patent_type", "country", "legal_status"]
        },
        "empty_tables": [name for name in TABLE_NAMES if sample[name].empty],
        "notes": [
            "Development sample only; not a statistically representative sample of the 106,393 patents.",
            "Base is proportional by patent type, then by primary topic domain and application-year cohort; rare cells may be absent.",
            "Citation closure deliberately over-represents cited patents so CITES edges and short chains exist for development.",
            "Designs keep no IPC / topic / efficacy rows, matching the full tables.",
            "All values are copied from data/processed; no field is imputed.",
        ],
    }
    (target / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    delivery = DATA_DIR.parent / "交付给同伴的内容" / "P1-6_真实样例"
    delivery.mkdir(parents=True, exist_ok=True)
    for name in TABLE_NAMES:
        sample[name].to_parquet(delivery / f"{name}.parquet", index=False)
    (delivery / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    trace.to_csv(delivery / "sample_selection.csv", index=False, encoding="utf-8-sig")

    readme = f"""# P1-6 真实样例（300—500 条，七表同步）

生成时间：{summary['generated_at']}
来源：`data/processed/*.parquet`（全量契约 C 七表），随机种子 `{SEED}`。

## 怎么用

```bash
python -m scripts.seed_sample   # 可选：按同一规则重建 data/_sample
python -m eval.check_contracts
python -m eval.smoke_test
python -m streamlit run app.py
```

默认 `USE_SAMPLE=true` 直接读取 `data/_sample/`。要跑全量，设置 `USE_SAMPLE=false`。

## 规模

| 表 | 行数 |
|---|---:|
""" + "\n".join(f"| `{name}` | {len(table):,} |" for name, table in sample.items()) + f"""

- 专利 {len(pat):,} 件：发明授权 {summary['patents_by_type'].get('发明授权', 0):,}、实用新型 {summary['patents_by_type'].get('实用新型', 0):,}、发明申请 {summary['patents_by_type'].get('发明申请', 0):,}、外观设计 {summary['patents_by_type'].get('外观设计', 0):,}。
- 非外观设计 {len(non_design):,} 件：IPC {summary['coverage']['with_ipc_pct']}%、主题 {summary['coverage']['with_topic_pct']}%、功效 {summary['coverage']['with_efficacy_pct']}%。
- 多申请人专利 {len(multi):,} 件；合作边 {len(co):,} 条。
- 引用边 {len(cites):,} 条，其中样本内 {in_edges:,} 条（{summary['citations_sample']['in_sample_pct']}%），外部 {len(cites)-in_edges:,} 条。

## 选择规则

1. 基础集 **{len(base)} 件**：按专利类型比例分配，再按主主题领域、申请年段分层抽样。
2. 引用闭包一 **{len(closure_1)} 件**：基础集专利引用最多的样本内专利。
3. 引用闭包二 **{len(closure_2)} 件**：闭包一专利引用最多的样本内专利，形成短引用链。
4. 七表按同一 `patent_id` 集合过滤；`cooperation` 由样例内申请人重新两两配对生成，权重等于共同专利数。

选择明细见 `sample_selection.csv`；完整统计见 `manifest.json`。

## 边界

- 这是**开发样例**，不是统计抽样，不能用于对外规模/趋势结论；全量数字看 `data/results/scale.json` 与 `docs/data_profile.md`。
- 引用闭包故意多选被引专利，保证样例内有 82 条 CITES 边和短引用链；这些边占样例全部引用边的 4.5%，低于全量的 7.9%，因为样例中的引用多数指向全量外部专利。
- 外观设计没有 IPC/主题/功效行，与全量口径一致。
- 所有字段都来自 `data/processed`，没有插值或伪造；缺失字段保留空值。
"""
    (delivery / "说明.md").write_text(readme, encoding="utf-8")

    print(json.dumps({
        "patents": len(pat),
        "base": len(base),
        "closure_1": len(closure_1),
        "closure_2": len(closure_2),
        "tables": summary["tables"],
        "in_sample_citation_edges": in_edges,
        "cooperation_edges": len(co),
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
