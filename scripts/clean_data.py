"""P1: clean the merged raw workbook into contract-C patents/applicants tables.

Rules:
- drop non-primary publication types when the application has a primary record
- deduplicate by application number, keep one representative publication
- representative priority: 发明授权 > 发明申请 > 实用新型 > 外观设计
- applicant: split multi-values, strip [] and -C/-U/-R/-G, dedupe per patent
- missing is null, never 0 or a guessed date
"""
import argparse
import json
import re
import shutil
import time
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from core import config

RAW_FILE = config.DATA_DIR / "raw" / "原始专利汇总.xlsx"
SAMPLE_FILE = config.RESULTS_DIR / "raw_sample_1000.parquet"
PROCESSED_DIR = config.PROCESSED_DIR
DELIVERY_DIR = config.ROOT_DIR / "交付给同伴的内容" / "P1-2_清洗主表"

NON_PRIMARY = {"译文", "检索报告", "修正或者更正专利", "短期专利", "其他"}
TYPE_PRIORITY = {"发明授权": 4, "发明申请": 3, "实用新型": 2, "外观设计": 1}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SUFFIX_RE = re.compile(r"-[A-Za-z]$")

PATENT_COLUMNS = ["patent_id", "title", "abstract", "apply_date", "apply_year",
                  "pub_date", "patent_type", "country", "legal_status", "is_in_sample"]
APPLICANT_COLUMNS = ["patent_id", "applicant_raw", "applicant_std",
                     "applicant_type", "is_first"]

KEYS = {
    "pid": "公开（公告）号", "appno": "申请号", "pubtype": "公开类型",
    "ptype": "专利类型", "country": "公开国别", "title": "标题 (中文)",
    "abstract": "摘要 (中文)", "appdate": "申请日", "pubdate": "公开（公告）日",
    "legal": "当前法律状态", "applicants": "申请人", "std_app": "标准化申请人",
    "first_app": "第一申请人", "app_type": "申请人类型",
    "app_country": "申请人国家/地区",
}


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


def clean_std(v) -> str:
    x = s(v).strip().strip("[]").strip()
    x = SUFFIX_RE.sub("", x).strip()
    return x


def norm_date(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    x = s(v)
    if len(x) >= 10 and DATE_RE.match(x[:10]):
        return x[:10]
    return None


def iter_xlsx(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    ws.reset_dimensions()
    it = ws.iter_rows(values_only=True)
    header = [s(x) for x in next(it)]
    idx = {name: i for i, name in enumerate(header)}
    for row in it:
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        yield {k: (row[idx[name]] if name in idx and idx[name] < len(row) else None)
               for k, name in KEYS.items()}
    wb.close()


def iter_sample(path):
    df = pd.read_parquet(path)
    for rec in df.to_dict("records"):
        yield {k: rec.get(name) for k, name in KEYS.items()}


def build_pairs(raw_parts, std_parts):
    pairs = []
    n = max(len(raw_parts), len(std_parts))
    for i in range(n):
        r = raw_parts[i] if i < len(raw_parts) else ""
        st = std_parts[i] if i < len(std_parts) else ""
        if not st and r:
            st = clean_std(r)
        if not r and st:
            r = st
        if not st and not r:
            continue
        pairs.append((r, st))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="use the 1,008-row sample")
    args = ap.parse_args()

    t0 = time.time()
    source = SAMPLE_FILE if args.sample else RAW_FILE
    if not source.is_file():
        raise SystemExit(f"missing source: {source}")

    records = []
    non_primary_rows = 0
    for rec in (iter_sample(source) if args.sample else iter_xlsx(source)):
        if s(rec.get("pubtype")) in NON_PRIMARY:
            non_primary_rows += 1
        records.append(rec)
        if len(records) % 20000 == 0:
            print(f"  read={len(records)} elapsed={time.time()-t0:.0f}s", flush=True)

    groups = defaultdict(list)
    missing_pid = 0
    missing_appno = 0
    for rec in records:
        pid = s(rec.get("pid"))
        appno = s(rec.get("appno"))
        if not pid:
            missing_pid += 1
            continue
        if not appno:
            missing_appno += 1
            continue
        groups[appno].append(rec)

    patents = []
    applicants = []
    seen_rep = set()
    duplicate_rep_pid = 0
    groups_only_non_primary = 0
    date_anomalies = 0
    date_anomaly_samples = []
    pair_length_mismatch = 0
    patents_without_applicants = 0
    multi_applicant_patents = 0
    foreign_unknown = 0
    first_true = 0
    unique_applicants = set()
    by_type = Counter()

    for appno, group in groups.items():
        primary = [r for r in group if s(r.get("pubtype")) not in NON_PRIMARY]
        if primary:
            pool = primary
        else:
            pool = group
            groups_only_non_primary += 1

        def sort_key(r):
            ptype = s(r.get("ptype"))
            pri = TYPE_PRIORITY.get(ptype, 0)
            pub = norm_date(r.get("pubdate")) or "9999-99-99"
            return (-pri, pub, s(r.get("pid")))

        rep = min(pool, key=sort_key)
        pid = s(rep.get("pid"))
        if pid in seen_rep:
            duplicate_rep_pid += 1
            continue
        seen_rep.add(pid)

        apply_date = norm_date(rep.get("appdate"))
        pub_date = norm_date(rep.get("pubdate"))
        if apply_date and pub_date and apply_date > pub_date:
            date_anomalies += 1
            if len(date_anomaly_samples) < 5:
                date_anomaly_samples.append((pid, apply_date, pub_date))
            apply_date = None
        apply_year = int(apply_date[:4]) if apply_date else None

        ptype = s(rep.get("ptype")) or None
        by_type[ptype or "(空)"] += 1
        patents.append({
            "patent_id": pid,
            "title": s(rep.get("title")) or None,
            "abstract": s(rep.get("abstract")) or None,
            "apply_date": apply_date,
            "apply_year": apply_year,
            "pub_date": pub_date,
            "patent_type": ptype,
            "country": s(rep.get("country")) or None,
            "legal_status": s(rep.get("legal")) or None,
            "is_in_sample": True,
        })

        raw_parts = split_multi(rep.get("applicants"))
        std_parts = [x for x in (clean_std(v) for v in split_multi(rep.get("std_app"))) if x]
        if len(raw_parts) != len(std_parts):
            pair_length_mismatch += 1
        pairs = build_pairs(raw_parts, std_parts)

        type_parts = [x.strip() for x in re.split(r"[,，;；]", s(rep.get("app_type"))) if x.strip()]
        if len(type_parts) == len(pairs):
            pair_types = type_parts
        elif len(type_parts) == 1:
            pair_types = [type_parts[0]] * len(pairs)
        else:
            pair_types = [None] * len(pairs)

        app_country = s(rep.get("app_country"))
        seen_std = set()
        kept = []
        for (r, st), t in zip(pairs, pair_types):
            key = st or r
            if not key or key in seen_std:
                continue
            seen_std.add(key)
            if not t and app_country and app_country != "中国":
                t = "境外/未知"
                foreign_unknown += 1
            kept.append((r or st, st or r, t))

        if not kept:
            patents_without_applicants += 1
            continue
        if len(kept) > 1:
            multi_applicant_patents += 1

        first = s(rep.get("first_app"))
        flags = [False] * len(kept)
        if first:
            for i, (r, st, _) in enumerate(kept):
                if first == r or first == st:
                    flags[i] = True
                    break
            else:
                for i, (r, st, _) in enumerate(kept):
                    if first in r or r in first:
                        flags[i] = True
                        break
            if not any(flags):
                flags[0] = True
        else:
            flags[0] = True

        for (r, st, t), is_first in zip(kept, flags):
            unique_applicants.add(st)
            if is_first:
                first_true += 1
            applicants.append({
                "patent_id": pid,
                "applicant_raw": r or None,
                "applicant_std": st or None,
                "applicant_type": t or None,
                "is_first": is_first,
            })

    patents_df = pd.DataFrame(patents, columns=PATENT_COLUMNS)
    for col in ["patent_id", "title", "abstract", "apply_date", "pub_date",
                "patent_type", "country", "legal_status"]:
        patents_df[col] = patents_df[col].astype("string")
    patents_df["apply_year"] = pd.array(patents_df["apply_year"], dtype="Int64")
    patents_df["is_in_sample"] = patents_df["is_in_sample"].astype(bool)

    applicants_df = pd.DataFrame(applicants, columns=APPLICANT_COLUMNS)
    for col in ["patent_id", "applicant_raw", "applicant_std", "applicant_type"]:
        applicants_df[col] = applicants_df[col].astype("string")
    applicants_df["is_first"] = applicants_df["is_first"].astype("boolean")

    if args.sample:
        out_dir = config.RESULTS_DIR / "_clean_sample"
        counts_path = config.RESULTS_DIR / "clean_counts_sample.json"
    else:
        out_dir = PROCESSED_DIR
        counts_path = config.RESULTS_DIR / "clean_counts.json"

    out_dir.mkdir(parents=True, exist_ok=True)
    patents_df.to_parquet(out_dir / "patents.parquet", index=False)
    applicants_df.to_parquet(out_dir / "applicants.parquet", index=False)

    counts = {
        "source": str(source),
        "sample_mode": args.sample,
        "raw_rows": len(records),
        "non_primary_rows": non_primary_rows,
        "applications": len(groups),
        "patents": len(patents_df),
        "patents_by_type": dict(by_type),
        "design_patents": by_type.get("外观设计", 0),
        "missing_pid": missing_pid,
        "missing_appno": missing_appno,
        "duplicate_representative_pid": duplicate_rep_pid,
        "groups_only_non_primary": groups_only_non_primary,
        "date_anomalies_nulled": date_anomalies,
        "date_anomaly_samples": date_anomaly_samples,
        "applicants_rows": len(applicants_df),
        "unique_applicants": len(unique_applicants),
        "patents_without_applicants": patents_without_applicants,
        "multi_applicant_patents": multi_applicant_patents,
        "applicant_pair_length_mismatch": pair_length_mismatch,
        "applicant_type_foreign_unknown": foreign_unknown,
        "first_applicant_true": first_true,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    counts_path.parent.mkdir(parents=True, exist_ok=True)
    counts_path.write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.sample:
        DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("patents.parquet", "applicants.parquet"):
            shutil.copy2(out_dir / name, DELIVERY_DIR / name)
        shutil.copy2(counts_path, DELIVERY_DIR / "clean_counts.json")
        readme = f"""# P1-2 清洗主表

生成时间：{datetime.now().isoformat(timespec='seconds')}
来源：`{RAW_FILE.name}`（{counts['raw_rows']:,} 行 × 204 列）

## 文件

| 文件 | 行 × 列 | 说明 |
|---|---|---|
| `patents.parquet` | {counts['patents']:,} × {len(PATENT_COLUMNS)} | 契约 C 的专利主表 |
| `applicants.parquet` | {counts['applicants_rows']:,} × {len(APPLICANT_COLUMNS)} | 契约 C 的申请关系表 |
| `clean_counts.json` | — | 清洗计数与异常记录 |

## 口径

- 按 `申请号` 去重，`patent_id` 为代表 `公开号`。
- 代表优先级：发明授权 > 发明申请 > 实用新型 > 外观设计；同类型取最早公开。
- 有主文献时丢弃译文/检索报告/修正/短期/其他；只有非主文献的申请保留。
- 外观设计保留在 `patents`，但没有 IPC/主题（P1-3 处理）。
- 申请日 > 公开日的 {counts['date_anomalies_nulled']} 条记录，申请日/申请年置空，公开日保留。
- 申请人按分号拆分，去 `[]`、去 `-C/-U/-R/-G`，同一专利内去重。
- 境外申请人类型空值填 `境外/未知`；中国申请人空值保持 null。
- 缺失一律 null，不填 0、不猜日期。

## 关键计数

- 原始行：{counts['raw_rows']:,}
- 非主文献行：{counts['non_primary_rows']:,}
- 去重后专利：{counts['patents']:,}（申请号 {counts['applications']:,} 个）
- 申请关系：{counts['applicants_rows']:,} 行；唯一标准化申请人 {counts['unique_applicants']:,}
- 无申请人专利：{counts['patents_without_applicants']:,}
- 多申请人专利：{counts['multi_applicant_patents']:,}
- 申请日异常置空：{counts['date_anomalies_nulled']:,}

## 局限

- 标准化申请人已去 `-C/-U/-R/-G` 后缀；仍存在 `重庆长安3`、`中国南方` 这类归并错误，Top 50 需人工别名表（P1-8 质量评估时处理）。
- {counts['groups_only_non_primary']:,} 个申请只有非主文献，保留其非主文献作为代表。
- {counts['applicant_pair_length_mismatch']:,} 件专利的原始/标准化申请人数不一致，按位置对齐，可能有错位。
- {counts['patents_without_applicants']:,} 件专利无申请人，申请关系表无对应行。
- 目前只有 patents/applicants 两张表；IPC、主题、功效、引用、合作在 P1-3/P1-4 生成。
- 本表默认全量，不在 `data/_sample`；页面仍用 `USE_SAMPLE=true` 的旧样例，P1-6 再重建样例。
"""
        (DELIVERY_DIR / "说明.md").write_text(readme, encoding="utf-8")

    print("written", out_dir / "patents.parquet", out_dir / "applicants.parquet")
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print("elapsed", counts["elapsed_sec"])


if __name__ == "__main__":
    main()
