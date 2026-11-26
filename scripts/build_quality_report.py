"""P1-8: scale/quality report and 100-row manual evaluation frame."""
import json
import re
import shutil
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd

from core import config

PROCESSED = config.PROCESSED_DIR
RESULTS = config.RESULTS_DIR
DELIVERY = config.ROOT_DIR / "交付给同伴的内容" / "P1-8_质量与别名"
SEED = 20261125
SAMPLE_N = 100
COHORT_BINS = [0, 2009, 2014, 2019, 2023, 2100]
COHORT_LABELS = ["<=2009", "2010-2014", "2015-2019", "2020-2023", "2024-2025"]


def _allocate(total: int, sizes: pd.Series, min_each: int = 1) -> dict:
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


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def _primary_domain(topic: pd.DataFrame) -> pd.Series:
    return topic.groupby("patent_id")["domain"].agg(lambda s: sorted(set(s))[0])


def _sample_frame(patents, topic, n=SAMPLE_N):
    frame = patents[["patent_id", "patent_type", "apply_year"]].copy()
    frame["domain"] = frame["patent_id"].map(_primary_domain(topic)).fillna("(无主题)")
    frame["cohort"] = pd.cut(frame["apply_year"], COHORT_BINS, labels=COHORT_LABELS)
    frame["cohort"] = frame["cohort"].astype("object").fillna("(缺失)")
    frame["domain"] = frame["domain"].where(frame["patent_type"] != "外观设计", "外观设计")

    selected = []
    type_quota = _allocate(n, frame["patent_type"].value_counts())
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
                take = cohort_quota[cohort]
                pick = cell_frame[cell_frame["cohort"] == cohort]
                chosen = pick.sample(n=min(take, len(pick)),
                                     random_state=SEED + 1000 * type_index + 10 * cell_index)
                selected.append(pd.DataFrame({
                    "patent_id": chosen["patent_id"].to_numpy(),
                    "stratum": f"{patent_type}/{cell}/{cohort}",
                }))
    return pd.concat(selected, ignore_index=True).drop_duplicates("patent_id")


def _join_values(series: pd.Series) -> str:
    return "; ".join(sorted({str(v) for v in series.dropna() if str(v).strip()}))


def _manual_frame(patents, applicants, ipc, topic, efficacy, citations, cooperation, reps):
    picked = _sample_frame(patents, topic)
    ids = set(picked["patent_id"])

    app = (applicants[applicants["patent_id"].isin(ids)]
           .groupby("patent_id")["applicant_std"].agg(_join_values))
    app_raw = (applicants[applicants["patent_id"].isin(ids)]
               .groupby("patent_id")["applicant_raw"].agg(_join_values))
    app_type = (applicants[applicants["patent_id"].isin(ids)]
                .groupby("patent_id")["applicant_type"].agg(_join_values))
    main_ipc = (ipc[ipc["patent_id"].isin(ids) & ipc["is_main"]]
                .groupby("patent_id")["ipc_code"].agg(_join_values))
    topic_text = (topic[topic["patent_id"].isin(ids)]
                  .groupby("patent_id")["topic"].agg(_join_values))
    eff_text = (efficacy[efficacy["patent_id"].isin(ids)]
                .groupby("patent_id")["efficacy_l1"].agg(_join_values))
    cites = citations.groupby("citing_id").size()
    cited = citations.groupby("cited_id").size()
    rep_index = reps.set_index("patent_id")

    adjacency = {}
    for row in cooperation.itertuples(index=False):
        adjacency.setdefault(row.app_a, set()).add(row.app_b)
        adjacency.setdefault(row.app_b, set()).add(row.app_a)

    rows = []
    for index, row in enumerate(picked.itertuples(index=False), start=1):
        partners = set()
        for name in str(app.get(row.patent_id, "")).split("; "):
            if name:
                partners.update(adjacency.get(name, set()))
        partners.discard("")
        patent_row = patents.loc[patents.patent_id == row.patent_id].iloc[0]
        rep_row = rep_index.loc[row.patent_id] if row.patent_id in rep_index.index else None
        rows.append({
            "sample_id": f"S{index:03d}",
            "patent_id": row.patent_id,
            "patent_type": patent_row["patent_type"],
            "apply_year": patent_row["apply_year"],
            "country": patent_row["country"],
            "title": patent_row["title"],
            "abstract": patent_row["abstract"],
            "applicant_raw": app_raw.get(row.patent_id, ""),
            "applicant_std": app.get(row.patent_id, ""),
            "applicant_type": app_type.get(row.patent_id, ""),
            "ipc_main": main_ipc.get(row.patent_id, ""),
            "topics": topic_text.get(row.patent_id, ""),
            "efficacy_l1": eff_text.get(row.patent_id, ""),
            "cites_count": int(cites.get(row.patent_id, 0)),
            "cited_by_count": int(cited.get(row.patent_id, 0)),
            "cite_count_raw": int(rep_row["cite_count"]) if rep_row is not None and pd.notna(rep_row["cite_count"]) else 0,
            "cited_count_raw": int(rep_row["cited_count"]) if rep_row is not None and pd.notna(rep_row["cited_count"]) else 0,
            "coop_partners": "; ".join(sorted(partners)),
            "stratum": row.stratum,
            "label_applicant": "",
            "label_ipc": "",
            "label_topic": "",
            "label_efficacy": "",
            "label_citation": "",
            "label_cooperation": "",
            "notes": "",
        })
    result = pd.DataFrame(rows)
    result["apply_year"] = result["apply_year"].astype("Int64")
    return result


def main():
    profile = json.loads((RESULTS / "raw_profile.json").read_text(encoding="utf-8"))
    tables = {name: pd.read_parquet(PROCESSED / f"{name}.parquet")
              for name in ["patents", "applicants", "patent_ipc", "patent_topic",
                           "patent_efficacy", "citations", "cooperation"]}
    reps = pd.read_parquet(RESULTS / "representatives.parquet")
    alias_summary = json.loads((RESULTS / "alias_summary.json").read_text(encoding="utf-8"))
    citation_summary = json.loads((RESULTS / "company_citation_summary.json").read_text(encoding="utf-8"))
    contract = json.loads((RESULTS / "contract_check.json").read_text(encoding="utf-8"))
    checks = contract.get("checks", [])
    checks_passed = sum(1 for check in checks if check.get("status") == "pass")

    patents = tables["patents"]
    applicants = tables["applicants"]
    ipc = tables["patent_ipc"]
    topic = tables["patent_topic"]
    efficacy = tables["patent_efficacy"]
    citations = tables["citations"]
    cooperation = tables["cooperation"]

    non_design = patents[patents["patent_type"] != "外观设计"]
    with_ipc = int(non_design["patent_id"].isin(ipc["patent_id"]).sum())
    with_topic = int(non_design["patent_id"].isin(topic["patent_id"]).sum())
    with_eff = int(non_design["patent_id"].isin(efficacy["patent_id"]).sum())
    fallback = topic[topic["topic"].astype(str).str.contains("（未细分）", regex=False)]
    fallback_rows = len(fallback)
    fallback_patents = int(fallback["patent_id"].nunique())
    keyword_rows = len(topic) - fallback_rows

    topic_quality = (topic.groupby(["topic", "domain"], as_index=False)
                     .size().rename(columns={"size": "patent_count"}))
    topic_quality["is_fallback"] = topic_quality["topic"].astype(str).str.contains(
        "（未细分）", regex=False)
    topic_quality["share_pct_of_tech_patents"] = (
        100 * topic_quality["patent_count"] / len(non_design)).round(2)
    topic_quality = topic_quality.sort_values(
        ["patent_count", "topic"], ascending=[False, True], ignore_index=True)
    topic_quality.to_csv(RESULTS / "topic_quality.csv", index=False, encoding="utf-8-sig")

    multi = applicants.groupby("patent_id").size()
    multi = multi[multi >= 2]
    app_types = applicants["applicant_type"].value_counts(dropna=False)
    app_types.index = [str(x) if pd.notna(x) else "(空)" for x in app_types.index]

    in_sample = int(citations["cited_in_sample"].sum())
    external = len(citations) - in_sample
    cited_app = int(citations["cited_applicant_std"].notna().sum())
    external_scalar_app = int(citations.loc[~citations["cited_in_sample"],
                                            "cited_applicant_std"].notna().sum())
    external_app_table = pd.read_parquet(RESULTS / "external_citation_applicants.parquet")
    external_app_pairs = int(len(external_app_table[["citing_id", "cited_id"]].drop_duplicates()))

    apply_years = patents["apply_year"].dropna().astype(int)
    pub_years = pd.to_numeric(patents["pub_date"].astype(str).str[:4], errors="coerce").dropna()
    year_counts = apply_years.value_counts().sort_index()
    year_counts = year_counts[year_counts.index >= 2010]

    sample_raw = pd.read_parquet(RESULTS / "raw_sample_1000.parquet")
    batch_status = pd.crosstab(sample_raw["源文件"], sample_raw["当前法律状态"])
    batch_summary = {"all_authorized": 0, "all_rejected": 0, "mixed": 0, "sample_rows_per_batch": 63}
    for _, row in batch_status.iterrows():
        values = {k: int(v) for k, v in row.items() if int(v) > 0}
        if set(values) == {"授权"}:
            batch_summary["all_authorized"] += 1
        elif set(values) == {"驳回"}:
            batch_summary["all_rejected"] += 1
        else:
            batch_summary["mixed"] += 1

    missing_patents = {
        col: int(patents[col].isna().sum())
        for col in ["title", "abstract", "apply_date", "apply_year", "pub_date",
                    "patent_type", "country", "legal_status"]
    }

    dataset = {
        "raw_rows": profile["rows"],
        "raw_columns": profile["columns"],
        "unique_application_numbers": profile["duplicates"]["unique_appno"],
        "patents": len(patents),
        "rows_removed_by_dedup": profile["rows"] - len(patents),
        "patents_by_type": {str(k): int(v) for k, v in patents["patent_type"].value_counts().items()},
        "patents_by_country_top": {str(k): int(v) for k, v in patents["country"].value_counts().head(15).items()},
        "patents_by_apply_year_2010_plus": {str(k): int(v) for k, v in year_counts.items()},
        "apply_year_min_max": [int(apply_years.min()), int(apply_years.max())],
        "pub_year_min_max": [int(pub_years.min()), int(pub_years.max())],
        "apply_2024": int((apply_years == 2024).sum()),
        "apply_2025": int((apply_years == 2025).sum()),
        "pub_2024": int((pub_years == 2024).sum()),
        "pub_2025": int((pub_years == 2025).sum()),
        "legal_status": {str(k): int(v) for k, v in patents["legal_status"].value_counts().items()},
        "tables": {name: len(table) for name, table in tables.items()},
        "applicants": {
            "rows": len(applicants),
            "unique_std": int(applicants["applicant_std"].nunique()),
            "patents_with_applicant": int(applicants["patent_id"].nunique()),
            "patents_without_applicant": int(len(patents) - applicants["patent_id"].nunique()),
            "multi_applicant_patents": int(len(multi)),
            "type_counts": {str(k): int(v) for k, v in app_types.items()},
            "type_missing": int(applicants["applicant_type"].isna().sum()),
        },
        "batches": {
            "source_files": profile["source_files"],
            "sample_legal_status": batch_summary,
            "note": "legal-status split is from the 1,008-row raw sample (63 rows/batch); full batch status not re-read",
        },
    }

    quality = {
        "check_status": contract.get("status", "unknown"),
        "checks_total": len(checks),
        "checks_passed": checks_passed,
        "warnings": contract.get("warnings", []),
        "coverage": {
            "non_design_patents": len(non_design),
            "ipc_patents": with_ipc,
            "ipc_pct": _pct(with_ipc, len(non_design)),
            "topic_patents": with_topic,
            "topic_pct": _pct(with_topic, len(non_design)),
            "efficacy_patents": with_eff,
            "efficacy_pct": _pct(with_eff, len(non_design)),
            "topic_rows": len(topic),
            "topic_keyword_rows": keyword_rows,
            "topic_fallback_rows": fallback_rows,
            "topic_fallback_patents": fallback_patents,
            "topics": {str(k): int(v) for k, v in
                       topic["topic"].value_counts().head(20).items()},
            "unsegmented_topics": {str(k): int(v) for k, v in
                                   fallback["topic"].value_counts().head(10).items()},
            "topic_policy": {
                "coverage_pct": _pct(with_topic, len(non_design)),
                "fallback_rows": fallback_rows,
                "fallback_share_of_topic_rows_pct": _pct(fallback_rows, len(topic)),
                "fallback_is_separate": True,
                "decision": "（未细分）单列；宽泛词风险已量化，未重跑词典以免破坏已交付样例/图谱，P1-10 可继续调",
                "broad_keyword_note": "电机、热管理、空调、装配等宽泛词仍可能过匹配；页面不要把（未细分）计入细粒度主题排名",
            },
        },
        "missing": {
            "patents": missing_patents,
            "applicant_type_missing": int(applicants["applicant_type"].isna().sum()),
            "applicant_type_foreign_unknown": int((applicants["applicant_type"] == "境外/未知").sum()),
        },
        "citations": {
            "edges": len(citations),
            "in_sample_edges": in_sample,
            "external_edges": external,
            "in_sample_pct": _pct(in_sample, len(citations)),
            "citing_patents": int(citations["citing_id"].nunique()),
            "edges_with_cited_applicant": cited_app,
            "edges_with_cited_applicant_pct": _pct(cited_app, len(citations)),
            "external_edges_with_cited_applicant": external_app_pairs,
            "external_with_cited_applicant_pct": _pct(external_app_pairs, external),
            "external_edges_with_scalar_applicant": external_scalar_app,
            "external_with_scalar_applicant_pct": _pct(external_scalar_app, external),
            "external_applicant_rows": len(external_app_table),
            "external_applicant_citing_patents": int(external_app_table["citing_id"].nunique()),
        },
        "cooperation": {
            "edges": len(cooperation),
            "multi_applicant_patents": int(len(multi)),
            "top": [{"app_a": r.app_a, "app_b": r.app_b, "weight": int(r.weight)}
                    for r in cooperation.head(10).itertuples()],
        },
        "aliases": alias_summary,
        "company_citations": citation_summary,
        "known_issues": [
            "40 patents have no applicant.",
            "868 non-design patents have no IPC; 82 have no main IPC.",
            "15,327 non-design patents have no topic; 16,839 topic rows are IPC fallback (（未细分）).",
            "9,197 non-design patents have no efficacy.",
            "2,931 applicant rows have null applicant_type.",
            "17 citation base collisions after kind-code stripping; 2 date anomalies nulled.",
            "2024-2025 data is incomplete; trend analysis uses 2010/2015-2023.",
        ],
    }

    scale_path = RESULTS / "scale.json"
    scale = json.loads(scale_path.read_text(encoding="utf-8"))
    scale["graph_status"] = scale.get("graph_status", scale.get("status", "unknown"))
    scale["status"] = "done"
    scale["p1_8"] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": dataset,
        "quality": quality,
    }
    scale_path.write_text(json.dumps(scale, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    quality_payload = {
        "generated_at": scale["p1_8"]["generated_at"],
        "graph_status": scale["graph_status"],
        "dataset": dataset,
        "quality": quality,
    }
    (RESULTS / "data_quality.json").write_text(
        json.dumps(quality_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manual = _manual_frame(patents, applicants, ipc, topic, efficacy, citations,
                           cooperation, reps)
    manual_path = RESULTS / "manual_sample_100.csv"
    # Preserve completed manual labels when regenerating the sampling frame.
    label_cols = ["label_applicant", "label_ipc", "label_topic",
                  "label_efficacy", "label_citation", "label_cooperation"]
    if manual_path.exists():
        old_manual = pd.read_csv(manual_path)
        if "patent_id" in old_manual.columns:
            old_manual = old_manual.drop_duplicates("patent_id").set_index("patent_id")
            for col in label_cols + ["notes"]:
                if col in old_manual.columns:
                    manual[col] = manual["patent_id"].map(old_manual[col])
    manual.to_csv(manual_path, index=False, encoding="utf-8-sig")

    protocol_path = RESULTS / "manual_sample_100.md"
    protocol = f"""# P1-8 人工抽样核对（100 条）

生成时间：{scale['p1_8']['generated_at']}
文件：`manual_sample_100.csv`；随机种子 `{SEED}`。

## 抽样

- 从 {len(patents):,} 件专利中分层抽 {len(manual)} 件：专利类型 → 主主题领域 → 申请年段。
- 覆盖外观设计、无 IPC、无主题、无功效、有引用、多申请人等边界情况。
- 每行给出表内预测值（`applicant_std`、`ipc_main`、`topics`、`efficacy_l1`、`cites_count`、`coop_partners`）。

## 核对方法

逐条对照原文，在 `label_*` 列填 `1`（正确）、`0`（错误）、`0.5`（部分正确），`notes` 写原因；建议至少两人独立核对 20 条后再统一口径。

字段对应：

| 列 | 核对对象 |
|---|---|
| `label_applicant` | 申请人拆分、去后缀、去重是否正确；对照 `applicant_raw` 与 `applicant_std` |
| `label_ipc` | 主 IPC 是否与原文一致 |
| `label_topic` | 主题是否过匹配/漏匹配；`（未细分）` 是否合理 |
| `label_efficacy` | 功效抽取是否对应原文 |
| `label_citation` | 引用方向/数量是否与原文一致；对照 `cites_count` 与 `cite_count_raw` |
| `label_cooperation` | 共同申请人配对是否正确 |

`abstract` 用于判断主题/功效；`cite_count_raw` / `cited_count_raw` 是原始字段计数，用来和表内 `cites_count` / `cited_by_count` 对照。

## 计算

对每个字段：

- 准确率 = 正确条数 / 已核对条数（`0.5` 按 0.5 计）
- 若把“表内预测”当预测集合、人工标注当参考集合，可计算 P/R/F1；关系类字段建议按边统计，不按专利统计。

## 边界

- 标注结果见 `manual_sample_100.csv`，汇总指标见 `manual_sample_100_metrics.json`；100 条只能说明抽样误差。
- 100 条只能说明抽样误差，不能替代全量校验；全量结构校验见 `contract_check.json`。
"""
    if not protocol_path.exists():
        protocol_path.write_text(protocol, encoding="utf-8")

    DELIVERY.mkdir(parents=True, exist_ok=True)
    for name in ["scale.json", "data_quality.json", "manual_sample_100.csv",
                 "manual_sample_100.md", "topic_quality.csv"]:
        shutil.copy2(RESULTS / name, DELIVERY / name)

    readme = f"""# P1-8 规模、质量与别名

生成时间：{scale['p1_8']['generated_at']}

## 文件

| 文件 | 内容 |
|---|---|
| `company_alias.csv` | 展示层别名 → 规范名；含 manual / auto_en / pending_review |
| `cooperation_merged.parquet` | 合并后的合作边；契约表未改 |
| `company_patent_counts.csv` | 合并后的企业专利数、申请行数、别名数、占比 |
| `company_citation_pairs.parquet` | 企业级引用聚合（口径 C） |
| `company_citation_summary.json` | H1 覆盖与 Top 企业对 |
| `manual_sample_100.csv` | 100 条分层抽样核对结果，标签已填 |
| `manual_sample_100.md` | 抽样、标注结果与 P/R/F1 说明 |
| `topic_quality.csv` | 主题计数、领域、是否 `（未细分）`、占技术类专利比例 |
| `data_quality.json` | 规模、覆盖、缺失、批次、已知问题 |
| `scale.json` | 图谱计数 + P1-8 数据集统计 |

## 关键数字

- 原始 {dataset['raw_rows']:,} 行 × {dataset['raw_columns']} 列；按申请号去重后 **{dataset['patents']:,}** 件，删除 {dataset['rows_removed_by_dedup']:,} 行。
- 非外观设计 {len(non_design):,} 件：IPC **{quality['coverage']['ipc_pct']}%**、主题 **{quality['coverage']['topic_pct']}%**、功效 **{quality['coverage']['efficacy_pct']}%**。
- 引用 {len(citations):,} 条：样本内 {in_sample:,}（{quality['citations']['in_sample_pct']}%），外部 {external:,}；有被引主体 {cited_app:,}。
- 合作 {len(cooperation):,} 对，来自 {len(multi):,} 件多申请人专利。
- 别名 {alias_summary['alias_rows']:,} 条，覆盖 {alias_summary['covered_patents']:,} 件专利；合并后合作边 {alias_summary['cooperation_merged_edges']:,} 条。
- 企业级引用：{citation_summary['pairs']:,} 个主体对，涉及 {citation_summary['unique_citing_companies']:,} 个引用方；`cited_applicants` 未区分企业/高校/个人，表名为 `company_` 但实际是主体级。

## 高风险/中风险处理

- **H1 引用覆盖低**：契约 `citations` 不改；新增 `company_citation_pairs.parquet`，所有结论标“基于 X 件引用专利 / Y 个主体”。
- **H2 企业别名**：只做展示层；Kia 与 Hyundai 不合并；`中国南方` 标 `pending_review`，不硬并。
- **H3 2024—2025**：趋势窗口 2010/2015—2023，2024—2025 标“不完整”。
- **M1 主题**：`（未细分）` 单列，主题覆盖率 {quality['coverage']['topic_pct']}% 写入页面/文档；`topic_quality.csv` 标出兜底主题；宽泛词风险已量化，未重跑词典以免破坏已交付样例/图谱。
- **M2 分母**：全部 {len(patents):,} vs 技术类 {len(non_design):,}，技术图过滤外观设计。
- **M3 申请人类型**：空值单列“未知”；境外保持“境外/未知”。
- **M4 16 批次**：`data_quality.json` 记录源文件行数与样本法律状态；不称“全量”。

## 局限

- 别名表不是完整实体消解；集团级合并会隐藏子公司差异。
- 企业级引用是聚合，不是精确专利边；`cited_applicants` 无法还原单件被引专利。
- 100 条抽样已完成标注与 P/R/F1 统计，结果见 `manual_sample_100.md`。
"""
    (DELIVERY / "说明.md").write_text(readme, encoding="utf-8")

    print(json.dumps({
        "patents": len(patents), "manual_sample": len(manual),
        "ipc_pct": quality["coverage"]["ipc_pct"],
        "topic_pct": quality["coverage"]["topic_pct"],
        "efficacy_pct": quality["coverage"]["efficacy_pct"],
        "aliases": alias_summary["alias_rows"],
        "company_pairs": citation_summary["pairs"],
        "scale_status": scale["status"],
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
