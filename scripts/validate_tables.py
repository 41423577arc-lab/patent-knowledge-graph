"""P1-5: validate all seven contract tables in data/processed.

Runs with USE_SAMPLE=false, loads through core.data_loader.load_table, and
checks columns, uniqueness, foreign keys, nulls, dtypes and relation counts.
Writes data/results/contract_check.json and docs/contract_check.md.
"""
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

os.environ["USE_SAMPLE"] = "false"

import pandas as pd

from core import config
from core.data_loader import TABLE_COLUMNS, available_tables, load_table

RESULTS_DIR = config.RESULTS_DIR
CHECK_JSON = RESULTS_DIR / "contract_check.json"
CHECK_MD = config.ROOT_DIR / "docs" / "contract_check.md"
DELIVERY_DIR = config.ROOT_DIR / "交付给同伴的内容" / "P1-5_七表校验"


def main():
    t0 = time.time()
    if config.USE_SAMPLE:
        raise SystemExit("validation must run with USE_SAMPLE=false")

    checks = []
    warnings = []
    tables = {}
    load_errors = {}

    def add(name, ok, detail, level="fail"):
        checks.append({
            "name": name,
            "status": "pass" if ok else level,
            "detail": detail,
        })

    available = set(available_tables())
    add("seven_tables_available", available == set(TABLE_COLUMNS),
        f"available={sorted(available)}")

    for name, cols in TABLE_COLUMNS.items():
        try:
            df = load_table(name)
            tables[name] = df
            add(f"{name}_columns", list(df.columns) == cols,
                f"rows={len(df)}, cols={len(df.columns)}")
        except Exception as exc:
            load_errors[name] = str(exc)
            add(f"{name}_load", False, str(exc))

    if load_errors:
        # Cannot continue structural checks without all tables.
        result = {
            "status": "fail",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "use_sample": False,
            "load_errors": load_errors,
            "checks": checks,
            "warnings": warnings,
        }
        CHECK_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("FAILED TO LOAD", load_errors)
        raise SystemExit(1)

    patents = tables["patents"]
    applicants = tables["applicants"]
    ipc = tables["patent_ipc"]
    topic = tables["patent_topic"]
    eff = tables["patent_efficacy"]
    citations = tables["citations"]
    cooperation = tables["cooperation"]

    pid_set = set(patents["patent_id"].dropna().astype(str))

    # patents
    add("patents_patent_id_unique", patents["patent_id"].is_unique,
        f"rows={len(patents)}, unique={patents['patent_id'].nunique()}")
    add("patents_patent_id_nonnull", int(patents["patent_id"].isna().sum()) == 0,
        f"null={int(patents['patent_id'].isna().sum())}")

    # applicants
    add("applicants_fk", set(applicants["patent_id"].dropna().astype(str)).issubset(pid_set),
        f"orphans={len(set(applicants['patent_id'].dropna().astype(str)) - pid_set)}")
    add("applicants_required_nonnull",
        int(applicants[["patent_id", "applicant_std", "is_first"]].isna().sum().sum()) == 0,
        f"nulls={applicants[['patent_id', 'applicant_std', 'is_first']].isna().sum().to_dict()}")
    add("applicants_no_duplicate_pair",
        int(applicants.duplicated(["patent_id", "applicant_std"]).sum()) == 0,
        f"dups={int(applicants.duplicated(['patent_id', 'applicant_std']).sum())}")
    first_sum = applicants.groupby("patent_id")["is_first"].sum()
    add("applicants_one_first_per_patent", bool((first_sum == 1).all()),
        f"groups={len(first_sum)}, bad={(first_sum != 1).sum()}")

    # ipc
    add("ipc_fk", set(ipc["patent_id"].dropna().astype(str)).issubset(pid_set),
        f"orphans={len(set(ipc['patent_id'].dropna().astype(str)) - pid_set)}")
    add("ipc_required_nonnull",
        int(ipc[["patent_id", "ipc_code", "is_main"]].isna().sum().sum()) == 0,
        f"nulls={ipc[['patent_id', 'ipc_code', 'is_main']].isna().sum().to_dict()}")
    add("ipc_no_duplicate_pair",
        int(ipc.duplicated(["patent_id", "ipc_code"]).sum()) == 0,
        f"dups={int(ipc.duplicated(['patent_id', 'ipc_code']).sum())}")
    main_sum = ipc.groupby("patent_id")["is_main"].sum()
    add("ipc_at_most_one_main", bool((main_sum <= 1).all()),
        f"groups={len(main_sum)}, bad={(main_sum > 1).sum()}")
    if int((main_sum == 0).sum()):
        warnings.append(f"{int((main_sum == 0).sum())} 件专利没有 is_main=True 的 IPC")

    # topic
    add("topic_fk", set(topic["patent_id"].dropna().astype(str)).issubset(pid_set),
        f"orphans={len(set(topic['patent_id'].dropna().astype(str)) - pid_set)}")
    add("topic_required_nonnull",
        int(topic[["patent_id", "topic", "domain"]].isna().sum().sum()) == 0,
        f"nulls={topic[['patent_id', 'topic', 'domain']].isna().sum().to_dict()}")
    add("topic_no_duplicate_pair",
        int(topic.duplicated(["patent_id", "topic"]).sum()) == 0,
        f"dups={int(topic.duplicated(['patent_id', 'topic']).sum())}")

    # efficacy
    add("efficacy_fk", set(eff["patent_id"].dropna().astype(str)).issubset(pid_set),
        f"orphans={len(set(eff['patent_id'].dropna().astype(str)) - pid_set)}")
    add("efficacy_required_nonnull", int(eff["patent_id"].isna().sum()) == 0,
        f"null patent_id={int(eff['patent_id'].isna().sum())}")
    content = eff[["efficacy_l1", "efficacy_l2", "efficacy_l3"]].notna().any(axis=1)
    add("efficacy_has_content", bool(content.all()),
        f"empty_rows={int((~content).sum())}")
    add("efficacy_no_duplicate_triple",
        int(eff.duplicated(["patent_id", "efficacy_l1", "efficacy_l2", "efficacy_l3"]).sum()) == 0,
        f"dups={int(eff.duplicated(['patent_id', 'efficacy_l1', 'efficacy_l2', 'efficacy_l3']).sum())}")

    # citations
    add("citations_citing_fk", set(citations["citing_id"].dropna().astype(str)).issubset(pid_set),
        f"orphans={len(set(citations['citing_id'].dropna().astype(str)) - pid_set)}")
    true_ids = set(citations.loc[citations["cited_in_sample"] == True, "cited_id"].dropna().astype(str))
    false_ids = set(citations.loc[citations["cited_in_sample"] == False, "cited_id"].dropna().astype(str))
    add("citations_true_cited_fk", true_ids.issubset(pid_set),
        f"orphans={len(true_ids - pid_set)}")
    add("citations_false_not_in_sample", len(false_ids & pid_set) == 0,
        f"overlap={len(false_ids & pid_set)}")
    add("citations_no_duplicate_edge",
        int(citations.duplicated(["citing_id", "cited_id"]).sum()) == 0,
        f"dups={int(citations.duplicated(['citing_id', 'cited_id']).sum())}")

    # cooperation
    applicant_set = set(applicants["applicant_std"].dropna().astype(str))
    add("cooperation_fk", set(cooperation["app_a"].dropna().astype(str)).issubset(applicant_set)
        and set(cooperation["app_b"].dropna().astype(str)).issubset(applicant_set),
        f"orphans_a={len(set(cooperation['app_a'].dropna().astype(str)) - applicant_set)}, "
        f"orphans_b={len(set(cooperation['app_b'].dropna().astype(str)) - applicant_set)}")
    add("cooperation_order", bool((cooperation["app_a"] < cooperation["app_b"]).all()),
        "app_a < app_b")
    add("cooperation_weight_positive", bool((cooperation["weight"] > 0).all()),
        f"min={cooperation['weight'].min()}, max={cooperation['weight'].max()}")
    add("cooperation_no_duplicate_pair",
        int(cooperation.duplicated(["app_a", "app_b"]).sum()) == 0,
        f"dups={int(cooperation.duplicated(['app_a', 'app_b']).sum())}")

    # dtypes
    dtype_checks = {
        "patents.apply_year": str(patents["apply_year"].dtype),
        "patents.is_in_sample": str(patents["is_in_sample"].dtype),
        "applicants.is_first": str(applicants["is_first"].dtype),
        "patent_ipc.is_main": str(ipc["is_main"].dtype),
        "citations.cited_in_sample": str(citations["cited_in_sample"].dtype),
        "cooperation.weight": str(cooperation["weight"].dtype),
    }
    add("dtypes", dtype_checks["patents.apply_year"].startswith("Int")
        and dtype_checks["patents.is_in_sample"] == "bool"
        and dtype_checks["applicants.is_first"] == "boolean"
        and dtype_checks["patent_ipc.is_main"] == "boolean"
        and dtype_checks["citations.cited_in_sample"] == "boolean"
        and dtype_checks["cooperation.weight"].startswith("int"),
        dtype_checks)

    patents_with_apps = applicants["patent_id"].nunique()
    patents_with_ipc = ipc["patent_id"].nunique()
    patents_with_topic = topic["patent_id"].nunique()
    patents_with_eff = eff["patent_id"].nunique()
    designs = int((patents["patent_type"] == "外观设计").sum())
    non_design = len(patents) - designs

    if len(patents) - patents_with_apps:
        warnings.append(f"{len(patents) - patents_with_apps} 件专利没有申请人")
    if non_design - patents_with_ipc:
        warnings.append(f"{non_design - patents_with_ipc} 件非外观设计没有 IPC")
    if non_design - patents_with_topic:
        warnings.append(f"{non_design - patents_with_topic} 件非外观设计没有主题")
    if non_design - patents_with_eff:
        warnings.append(f"{non_design - patents_with_eff} 件非外观设计没有功效")
    if int(applicants["applicant_type"].isna().sum()):
        warnings.append(f"{int(applicants['applicant_type'].isna().sum())} 条申请关系 applicant_type 为空")
    warnings.append(f"引用边 {len(citations):,}；样本内 {int((citations['cited_in_sample'] == True).sum()):,}；"
                    f"外部 {int((citations['cited_in_sample'] == False).sum()):,}")
    warnings.append("P1-5 只校验契约结构；数据质量抽样与别名表在 P1-8 处理。")

    failed = [c for c in checks if c["status"] == "fail"]
    status = "pass" if not failed else "fail"

    counts = {
        "patents": int(len(patents)),
        "patents_by_type": {str(k): int(v) for k, v in patents["patent_type"].value_counts(dropna=False).items()},
        "design_patents": designs,
        "non_design_patents": non_design,
        "applicants_rows": int(len(applicants)),
        "unique_applicants": int(applicants["applicant_std"].nunique()),
        "patents_with_applicants": int(patents_with_apps),
        "patent_ipc_rows": int(len(ipc)),
        "unique_ipc": int(ipc["ipc_code"].nunique()),
        "patents_with_ipc": int(patents_with_ipc),
        "patent_topic_rows": int(len(topic)),
        "unique_topics": int(topic["topic"].nunique()),
        "unique_domains": int(topic["domain"].nunique()),
        "patents_with_topic": int(patents_with_topic),
        "patent_efficacy_rows": int(len(eff)),
        "patents_with_efficacy": int(patents_with_eff),
        "citations_rows": int(len(citations)),
        "citations_in_sample": int((citations["cited_in_sample"] == True).sum()),
        "citations_external": int((citations["cited_in_sample"] == False).sum()),
        "citations_with_applicant": int(citations["cited_applicant_std"].notna().sum()),
        "cooperation_rows": int(len(cooperation)),
        "cooperation_max_weight": int(cooperation["weight"].max()),
    }

    result = {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "use_sample": False,
        "tables": {name: {"rows": len(df), "columns": list(df.columns),
                          "dtypes": {c: str(t) for c, t in df.dtypes.items()}}
                   for name, df in tables.items()},
        "checks": checks,
        "warnings": warnings,
        "counts": counts,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHECK_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 七表契约校验（P1-5）", "",
             f"状态：**{status.upper()}**", f"生成时间：{result['generated_at']}", "",
             f"数据目录：`data/processed/`（USE_SAMPLE=false）", "",
             "## 校验项", "", "| 检查 | 状态 | 详情 |", "|---|---|---|"]
    for c in checks:
        lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")
    lines += ["", "## 规模", "", "| 指标 | 数值 |", "|---|---:|"]
    for k, v in counts.items():
        if isinstance(v, dict):
            v = ", ".join(f"{a}:{b}" for a, b in v.items())
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 警告与说明", ""]
    for w in warnings:
        lines.append(f"- {w}")
    CHECK_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CHECK_JSON, DELIVERY_DIR / "contract_check.json")
    shutil.copy2(CHECK_MD, DELIVERY_DIR / "contract_check.md")

    print(f"status={status} checks={len(checks)} failed={len(failed)} warnings={len(warnings)}")
    for c in failed:
        print("FAIL", c["name"], c["detail"])
    print("written", CHECK_JSON, CHECK_MD)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
