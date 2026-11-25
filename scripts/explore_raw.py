"""P1: profile the merged raw workbook without inventing values.

Reads data/raw/原始专利汇总.xlsx once, writes:
- data/results/raw_profile.json
- docs/data_profile.md (draft)
- data/results/raw_sample_1000.parquet (about 1,008 rows, all columns)
"""
import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from core import config

RAW_FILE = config.DATA_DIR / "raw" / "原始专利汇总.xlsx"
RESULTS_DIR = config.RESULTS_DIR
PROFILE_JSON = RESULTS_DIR / "raw_profile.json"
PROFILE_MD = config.ROOT_DIR / "docs" / "data_profile.md"
SAMPLE_PARQUET = RESULTS_DIR / "raw_sample_1000.parquet"

SOURCE = "源文件"
PID = "公开（公告）号"
APPNO = "申请号"
APPDATE = "申请日"
PUBDATE = "公开（公告）日"
PTYPE = "专利类型"
PUBTYPE = "公开类型"
COUNTRY = "公开国别"
APPLICANTS = "申请人"
STD_APP = "标准化申请人"
APP_TYPE = "申请人类型"
IPC = "IPC"
IPC_MAIN = "IPC主分类"
CITE = "引证专利"
CITED = "被引证专利"
CITED_APP = "被引证申请人"
EFF = "技术功效短语"
LEGAL_VALID = "专利有效性"
LEGAL_STATUS = "当前法律状态"
TITLE = "标题 (中文)"
ABSTRACT = "摘要 (中文)"
VALUE = "合享价值度"

DIST_KEYS = [PTYPE, PUBTYPE, COUNTRY, APP_TYPE, LEGAL_VALID, LEGAL_STATUS,
             VALUE, "技术稳定性", "技术先进性", "保护范围"]
KEY_FIELDS = [PID, APPNO, TITLE, ABSTRACT, APPDATE, PUBDATE, APPLICANTS,
              STD_APP, APP_TYPE, IPC_MAIN, IPC, EFF, CITE, CITED, CITED_APP,
              "发明人", LEGAL_VALID, LEGAL_STATUS, VALUE]

KIND_RE = re.compile(r"[A-Z]\d*$")


def strip_kind(pid: str) -> str:
    return KIND_RE.sub("", pid)


def s(v) -> str:
    return "" if v is None else str(v).strip()


def pct(n, total):
    return round(n / total, 4) if total else None


def lens(values):
    if not values:
        return None
    arr = sorted(values)
    return {
        "n": len(arr),
        "min": arr[0],
        "p50": arr[len(arr) // 2],
        "p90": arr[int(len(arr) * 0.9)],
        "max": arr[-1],
    }


def main():
    if not RAW_FILE.is_file():
        raise SystemExit(f"missing raw file: {RAW_FILE}")

    t0 = time.time()
    wb = load_workbook(RAW_FILE, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    ws.reset_dimensions()
    it = ws.iter_rows(values_only=True)
    header = [s(x) for x in next(it)]
    ncols = len(header)
    idx = {name: i for i, name in enumerate(header)}
    for required in (SOURCE, PID, APPNO):
        if required not in idx:
            raise SystemExit(f"required column missing: {required}")

    nonempty = [0] * ncols
    max_len = [0] * ncols
    total = 0
    empty_rows = 0
    source_counter = Counter()
    pid_counter = Counter()
    appno_counter = Counter()
    cited_ids = set()
    apply_years = Counter()
    pub_years = Counter()
    date_anomalies = 0
    date_anomaly_samples = []
    multi = Counter()
    dist = {k: Counter() for k in DIST_KEYS}
    title_lens = []
    abstract_lens = []
    sample_rows = []
    sample_per_source = Counter()
    max_cell_len = 0

    for row in it:
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            empty_rows += 1
            continue
        total += 1
        vals = list(row) + [None] * (ncols - len(row))
        vals = vals[:ncols]

        for i, v in enumerate(vals):
            if v is not None and str(v).strip() != "":
                nonempty[i] += 1
            text = "" if v is None else str(v)
            if len(text) > max_len[i]:
                max_len[i] = len(text)
            if len(text) > max_cell_len:
                max_cell_len = len(text)

        def get(name):
            i = idx.get(name)
            return s(vals[i]) if i is not None else ""

        src = get(SOURCE)
        source_counter[src] += 1

        pid = get(PID)
        appno = get(APPNO)
        if pid:
            pid_counter[pid] += 1
        if appno:
            appno_counter[appno] += 1

        for name in DIST_KEYS:
            dist[name][get(name)] += 1

        ad = get(APPDATE)
        pd_ = get(PUBDATE)
        ay = ad[:4] if len(ad) >= 4 and ad[:4].isdigit() else ""
        py = pd_[:4] if len(pd_) >= 4 and pd_[:4].isdigit() else ""
        if ay:
            apply_years[int(ay)] += 1
        if py:
            pub_years[int(py)] += 1
        if ad and pd_ and ad > pd_:
            date_anomalies += 1
            if len(date_anomaly_samples) < 5:
                date_anomaly_samples.append((pid, ad, pd_))

        for name in (APPLICANTS, STD_APP, IPC, EFF, CITE, CITED):
            v = get(name)
            if ";" in v:
                multi[name + "_semicolon"] += 1

        cited = get(CITED)
        if cited:
            for x in re.split(r"[;；]", cited):
                x = x.strip()
                if x:
                    cited_ids.add(x)

        t = get(TITLE)
        a = get(ABSTRACT)
        if t:
            title_lens.append(len(t))
        if a:
            abstract_lens.append(len(a))

        if sample_per_source[src] < 63 and len(sample_rows) < 1008:
            sample_rows.append(vals)
            sample_per_source[src] += 1

        if total % 10000 == 0:
            print(f"  rows={total} elapsed={time.time()-t0:.0f}s", flush=True)

    wb.close()

    pid_set = set(pid_counter)
    pid_base = {strip_kind(p) for p in pid_set}
    cited_base = {strip_kind(p) for p in cited_ids}
    exact_hit = len(cited_ids & pid_set)
    # Count cited records whose kind-code-stripped form is in the sample.
    # (Set intersection would undercount when A/B versions collapse to one base.)
    base_hit = sum(1 for x in cited_ids if strip_kind(x) in pid_base)

    column_stats = []
    for i, name in enumerate(header):
        column_stats.append({
            "column": name,
            "nonempty": nonempty[i],
            "missing": total - nonempty[i],
            "missing_rate": pct(total - nonempty[i], total),
            "max_len": max_len[i],
        })

    key_missing = {name: {
        "nonempty": nonempty[idx[name]] if name in idx else None,
        "missing": total - nonempty[idx[name]] if name in idx else None,
        "missing_rate": pct(total - nonempty[idx[name]], total) if name in idx else None,
    } for name in KEY_FIELDS}

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raw_file": str(RAW_FILE),
        "rows": total,
        "columns": ncols,
        "empty_rows": empty_rows,
        "max_cell_length": max_cell_len,
        "source_files": dict(source_counter.most_common()),
        "key_missing": key_missing,
        "column_stats": column_stats,
        "distributions": {k: dict(v.most_common(20)) for k, v in dist.items()},
        "duplicates": {
            "unique_pid": len(pid_counter),
            "duplicate_pid_rows": sum(c - 1 for c in pid_counter.values() if c > 1),
            "unique_appno": len(appno_counter),
            "duplicate_appno_rows": sum(c - 1 for c in appno_counter.values() if c > 1),
            "appno_with_multiple_rows": sum(1 for c in appno_counter.values() if c > 1),
        },
        "citations": {
            "unique_cited_ids": len(cited_ids),
            "in_sample_exact": exact_hit,
            "in_sample_exact_rate": pct(exact_hit, len(cited_ids)),
            "in_sample_without_kind": base_hit,
            "in_sample_without_kind_rate": pct(base_hit, len(cited_ids)),
            "unique_cited_bases": len(cited_base),
            "rows_with_cite": nonempty[idx[CITE]] if CITE in idx else None,
            "rows_with_cited": nonempty[idx[CITED]] if CITED in idx else None,
            "rows_missing_cite": total - nonempty[idx[CITE]] if CITE in idx else None,
            "rows_missing_cited": total - nonempty[idx[CITED]] if CITED in idx else None,
        },
        "years": {
            "apply_year": dict(sorted(apply_years.items())),
            "pub_year": dict(sorted(pub_years.items())),
        },
        "lengths": {
            "title": lens(title_lens),
            "abstract": lens(abstract_lens),
        },
        "multi_value_rows": dict(multi),
        "date_anomalies": {
            "count": date_anomalies,
            "samples": date_anomaly_samples,
        },
        "sample": {
            "rows": len(sample_rows),
            "path": str(SAMPLE_PARQUET),
            "method": "每个源文件前 63 行，合计约 1,008 行",
        },
        "elapsed_sec": round(time.time() - t0, 1),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(sample_rows, columns=header).to_parquet(SAMPLE_PARQUET, index=False)

    # markdown draft
    def tbl_missing():
        rows = ["| 字段 | 缺失数 | 缺失率 |", "|---|---:|---:|"]
        for name in KEY_FIELDS:
            m = key_missing[name]
            if m["missing"] is None:
                continue
            rows.append(f"| {name} | {m['missing']:,} | {m['missing_rate']*100:.1f}% |")
        return "\n".join(rows)

    def tbl_dist(name):
        rows = ["| 值 | 数量 |", "|---|---:|"]
        for k, v in dist[name].most_common(12):
            rows.append(f"| {k or '(空)'} | {v:,} |")
        return "\n".join(rows)

    md = f"""# 原始数据探查（P1 草稿）

生成时间：{out['generated_at']}
数据文件：`{RAW_FILE.name}`（{total:,} 行 × {ncols} 列）

> 这是**原始汇总数据**的探查，不是契约 C 七张表。七张表在 P1-2~P1-5 生成。

## 1. 规模

| 指标 | 数值 |
|---|---:|
| 数据行 | {total:,} |
| 列数 | {ncols} |
| 空行 | {empty_rows} |
| 唯一公开号 | {len(pid_counter):,} |
| 重复公开号行 | {out['duplicates']['duplicate_pid_rows']:,} |
| 唯一申请号 | {len(appno_counter):,} |
| 重复申请号行 | {out['duplicates']['duplicate_appno_rows']:,} |
| 一个申请号多行 | {out['duplicates']['appno_with_multiple_rows']:,} |
| 最大单元格长度 | {max_cell_len:,} |

## 2. 关键字段缺失

{tbl_missing()}

## 3. 引用

- 被引证专利去重：{out['citations']['unique_cited_ids']:,}
- 精确匹配样本内：{out['citations']['in_sample_exact']:,}（{out['citations']['in_sample_exact_rate']*100:.1f}%）
- 去掉 kind code 后匹配：{out['citations']['in_sample_without_kind']:,}（{out['citations']['in_sample_without_kind_rate']*100:.1f}%）
- 有引证专利的行：{out['citations']['rows_with_cite']:,}
- 有被引证专利的行：{out['citations']['rows_with_cited']:,}
- 无引证专利的行：{out['citations']['rows_missing_cite']:,}
- 无被引证专利的行：{out['citations']['rows_missing_cited']:,}

## 4. 分布

### 专利类型

{tbl_dist(PTYPE)}

### 公开国别

{tbl_dist(COUNTRY)}

### 专利有效性

{tbl_dist(LEGAL_VALID)}

### 申请人类型

{tbl_dist(APP_TYPE)}

## 5. 年度

- 申请年：{min(apply_years) if apply_years else '-'}—{max(apply_years) if apply_years else '-'}
- 公开年：{min(pub_years) if pub_years else '-'}—{max(pub_years) if pub_years else '-'}
- 2024 申请：{apply_years.get(2024, 0):,}；2025 申请：{apply_years.get(2025, 0):,}（不完整）
- 2024 公开：{pub_years.get(2024, 0):,}；2025 公开：{pub_years.get(2025, 0):,}（不完整）

## 6. 多值字段

| 字段 | 含分号的行 |
|---|---:|
| 申请人 | {multi.get(APPLICANTS + '_semicolon', 0):,} |
| 标准化申请人 | {multi.get(STD_APP + '_semicolon', 0):,} |
| IPC | {multi.get(IPC + '_semicolon', 0):,} |
| 技术功效短语 | {multi.get(EFF + '_semicolon', 0):,} |
| 引证专利 | {multi.get(CITE + '_semicolon', 0):,} |
| 被引证专利 | {multi.get(CITED + '_semicolon', 0):,} |

## 7. 口径与局限

- 本文件是 16 个 xlsx 的原始合并，**未去重、未清洗**；46 行重复公开号保留。
- 同一申请号可能对应申请/授权多次公开，七张表会按申请号去重，不能直接用本表计数。
- 被引证专利只有约 1/8 能在样本内匹配；企业级引用分析要用 `被引证申请人` 聚合。
- 申请人类型缺失主要来自境外申请人；标准化申请人有 `-C/-U/-R/-G` 后缀和重复，P1-2 统一清洗。
- 外观设计没有 IPC，技术主题分析应排除。
- 2024—2025 年数据不完整，趋势分析用 2010/2015—2023。

## 8. 小闭环样本

- `{SAMPLE_PARQUET.name}`：{len(sample_rows)} 行 × {ncols} 列，每个源文件前 63 行，用于 P1-2 的读取/清洗自测。
"""
    PROFILE_MD.write_text(md, encoding="utf-8")

    print("written", PROFILE_JSON, PROFILE_MD, SAMPLE_PARQUET)
    print("rows", total, "cols", ncols, "elapsed", out["elapsed_sec"])


if __name__ == "__main__":
    main()
