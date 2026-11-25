"""P1-8 H2: display-level company alias table and merged views.

Contract tables are not modified.  The alias table merges only:
- clear Chinese/English variants of the same group,
- Incopat truncated names (e.g. 比亚迪司, 马自达司),
- a small set of explicit group-level names.

Kia and Hyundai stay separate.  ``中国南方`` is marked pending review and is
NOT hard-merged.  Outputs go to data/results and the P1-8 delivery folder.
"""
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from core import config

APPLICANTS = config.PROCESSED_DIR / "applicants.parquet"
COOPERATION = config.PROCESSED_DIR / "cooperation.parquet"
OUT_DIR = config.RESULTS_DIR
DELIVERY_DIR = config.ROOT_DIR / "交付给同伴的内容" / "P1-8_质量与别名"

# Curated group-level display names.  Keys must exist in applicant_std.
MANUAL = {
    # Korean: Kia and Hyundai MUST stay separate groups.
    "Kia Corporation": "起亚",
    "Kia Corp": "起亚",
    "Kia Motors Co., Ltd": "起亚",
    "Kia Motors Corp. Ltd.": "起亚",
    "Kia Motors Co., Ltd.": "起亚",
    "Kia Motors Corporaton": "起亚",
    "Kia Motor Corporation": "起亚",
    "Hyundai Motor Co.": "现代公司",
    "Hyundai Motor Company Co Ltd": "现代公司",
    "Hyundai Motor Co": "现代公司",
    # Japanese / German / US / Korean groups with Chinese canonical names.
    "丰田公司": "丰田公司",
    "Toyota Motor Engineering & Manufacturing North America, Inc.": "丰田公司",
    "Toyota Motor Engineering & Manufacturing North America Inc": "丰田公司",
    "Toyota Jidosha Kabushiki Kaisha": "丰田公司",
    "Toyota Chidosha Kabushiki Kaisha": "丰田公司",
    "Toyota Jidosha Kabusuiki Kaisha": "丰田公司",
    "本田公司": "本田公司",
    "Honda Motor Co.,  Ltd.": "本田公司",
    "日产公司": "日产公司",
    "Nissan Motor Co.,  Ltd.": "日产公司",
    "Nissan Motor Co.. Ltd.": "日产公司",
    "Nissan Motor Co.,  Ltd": "日产公司",
    "三菱公司": "三菱公司",
    "Mitsubishi Jidosha Engineering Kabushiki Kaisha": "三菱公司",
    "Mitsubishi Jidosha Engineering K.K.": "三菱公司",
    "Mitsubishi Jidosha Kogyo Kab": "三菱公司",
    "Mitsubishi Automob Eng Co Ltd": "三菱公司",
    "铃木汽车": "铃木汽车",
    "Suzuki Motor Corporation": "铃木汽车",
    "Suzuki Kabushiki Kaisha": "铃木汽车",
    "马自达司": "马自达",
    "Subaru Corp": "斯巴鲁",
    "Subaru Corporation": "斯巴鲁",
    "大众公司": "大众公司",
    "Volkswagen Ag, 38440, Wolfsburg, De": "大众公司",
    "宝马公司": "宝马公司",
    "Bayerische Motoren Werke Aktiengesellschaft, 80809, München, De": "宝马公司",
    "Bayerische Motorenwerk Ag": "宝马公司",
    "标致公司": "标致公司",
    "Peugeot Citroën Automobiles Société Anonyme": "标致公司",
    "雷诺公司": "雷诺公司",
    "Renault": "雷诺公司",
    "福特汽车": "福特汽车",
    "Ford Global Technologies, Inc.": "福特汽车",
    "Ford Global Technologies, Llc (N.D.Ges.D. Staates Delaware)": "福特汽车",
    "Ford Global Tech Dearborn": "福特汽车",
    "Ford-Werke Gmbh": "福特汽车",
    "特斯拉司": "特斯拉",
    # Toshiba / Costel / LG / Panasonic / Bosch / Denso / Sony / Hitachi
    "东芝公司": "东芝公司",
    "Toshiba Infrastructure Systems & Solution Corp": "东芝公司",
    "Toshiba Infrastructure Systems & Solutions Corporation": "东芝公司",
    "Toshiba Energy System&Solution Corp": "东芝公司",
    "东芝基础设施系统株式会社": "东芝公司",
    "东芝股份有限公司": "东芝公司",
    "日商东芝股份有限公司": "东芝公司",
    "日商东芝基础设施系统股份有限公司": "东芝公司",
    "日商东芝股份有限公司 (日本)": "东芝公司",
    "日商东芝基础设施系统股份有限公司 (日本)": "东芝公司",
    "Costel Co., Ltd.": "Costel",
    "Costel Co Ltd": "Costel",
    "코스텔(주)": "Costel",
    "Lg Energy Solution, Ltd.": "LG新能源",
    "Lg Energy Solution Ltd": "LG新能源",
    "Lg Energy Solution Ltd.": "LG新能源",
    "株式会社LG新能源": "LG新能源",
    "LG化学公司": "LG化学",
    "乐金集团": "LG",
    "松下集团": "松下集团",
    "Panasonic Corp": "松下集团",
    "Panasonic Corporation": "松下集团",
    "Panasonic Holdings Corp": "松下集团",
    "Panasonic Intellectual Property Management Co., Ltd.": "松下集团",
    "Panasonic Intellectual Property Management Co Ltd": "松下集团",
    "Panasonic Intellectual Property Management Co.,  Ltd.": "松下集团",
    "Panasonic Intellectual Propertymanagement Co., Ltd.": "松下集团",
    "Panasonic Ip Man Co Ltd": "松下集团",
    "Panasonic Ip Man Corp": "松下集团",
    "博世公司": "博世公司",
    "Robert Bosch Gesellschaft Mit Beschränkter Haftung": "博世公司",
    "Robert Bosch Gmbh": "博世公司",
    "Robert Bosch Gmbh, 70469, Stuttgart, De": "博世公司",
    "Bosch Corporation": "博世公司",
    "电装公司": "电装公司",
    "Nippondenso Co Ltd": "电装公司",
    "索尼公司": "索尼公司",
    "Sony Group Corporation": "索尼公司",
    "日立公司": "日立公司",
    "Hitachi Astemo Ltd": "日立公司",
    "Hitachi Astemo, Ltd.": "日立公司",
    "三星集团": "三星集团",
    "雅马哈株": "雅马哈",
    "Yamaha Hatsudoki Kabushiki Kaisha": "雅马哈",
    "村田株式": "村田",
    "Murata Manufacturing Co., Ltd.": "村田",
    "Murata Manufacturing Co": "村田",
    "Murata Manufacturing Co Ltd": "村田",
    "Murata Mfg Co Ltd": "村田",
    "Murata Manufacturing Co., Ltd": "村田",
    # Chinese truncation / Incopat artefacts.
    "比亚迪司": "比亚迪",
    "大陆商比亚迪股份有限公司": "比亚迪",
    "大陆商比亚迪股份有限公司 (中国大陆)": "比亚迪",
    "Shenzhen Byd Auto R&D Company Limited": "比亚迪",
    "Shenzhen Byd Auto R D Company Limited": "比亚迪",
    "Shenzhen Byd Auto R & D Co Ltd": "比亚迪",
    "比亚迪储": "比亚迪",
    "西门子司": "西门子",
    "Siemens Mobility Gmbh": "西门子",
    "法雷奥司": "法雷奥",
    "Valeo Eautomotive Germany Gmbh": "法雷奥",
    "Valeo Eautomotive France Sas": "法雷奥",
    "赛力斯集": "赛力斯",
    "赛力斯汽": "赛力斯",
    "奥动新能": "奥动新能源",
    "奥动新能源股份有限公司": "奥动新能源",
    "特来电新": "特来电新能源",
    "小刀新能": "小刀新能源",
    "小刀科技股份有限公司": "小刀新能源",
    "天津小刀电动科技股份有限公司": "小刀新能源",
    "合众新能": "合众新能源",
    "格罗夫氢": "格罗夫氢能",
    "小灵狗出": "小灵狗出行",
    "纳恩博北": "纳恩博",
    "纳恩博(常州)科技有限公司": "纳恩博",
    "新日电动": "新日",
    "新日无锡": "新日",
    "浙江零跑": "零跑汽车",
    "蔚来控股": "蔚来",
    "大陆商上海蔚来汽车有限公司": "蔚来",
    "大陆商蔚来(安徽)控股有限公司": "蔚来",
    "香港商蔚来汽车有限公司": "蔚来",
    "重庆长安3": "重庆长安",
    "安徽江淮2": "江淮汽车",
    "东风汽车2": "东风汽车",
}

PENDING_REVIEW = {
    "中国南方": "Incopat 疑似错误归并：大部分原始申请人为重庆长安新能源，需抽样核对，不硬并。",
}

LEGAL_SUFFIXES = [
    "corporation", "corp", "company", "co", "ltd", "limited", "inc",
    "gmbh", "ag", "plc", "holdings", "group", "kabushiki", "kaisha", "llc",
]
LEGAL_RE = re.compile(
    r"\b(corporation|corp|company|co|ltd|limited|inc|gmbh|ag|plc|llc|"
    r"holdings|group|kabushiki|kaisha|s\.?p\.?a)\b", re.IGNORECASE)


def is_ascii(name: str) -> bool:
    return all(ord(ch) < 128 for ch in name)


def has_legal_suffix(name: str) -> bool:
    return bool(LEGAL_RE.search(name))


def norm_en(name: str) -> str:
    value = re.sub(r"[^a-z0-9]", "", name.lower())
    changed = True
    while changed:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            if value.endswith(suffix) and len(value) > len(suffix):
                value = value[: -len(suffix)]
                changed = True
    return value


def resolve(name: str, alias: dict) -> str:
    seen = set()
    while name in alias and name not in seen:
        seen.add(name)
        name = alias[name]
    return name


def main():
    applicants = pd.read_parquet(APPLICANTS)
    cooperation = pd.read_parquet(COOPERATION)
    counts = applicants["applicant_std"].astype(str).value_counts()

    alias = {}
    method = {}
    rows = {}
    notes = {}
    missing_manual = []

    for name, canonical in MANUAL.items():
        if name in counts.index:
            if name != canonical:
                alias[name] = canonical
                method[name] = "manual"
                rows[name] = int(counts[name])
        else:
            missing_manual.append(name)

    for name, note in PENDING_REVIEW.items():
        if name in counts.index:
            method[name] = "pending_review"
            rows[name] = int(counts[name])
            notes[name] = note

    # Auto-merge only pure-ASCII names that differ by punctuation / legal suffix.
    groups = defaultdict(list)
    for name, count in counts.items():
        name = str(name)
        if name in alias or name in method or not is_ascii(name):
            continue
        if not has_legal_suffix(name):
            continue
        key = norm_en(name)
        if len(key) < 4:
            continue
        groups[key].append((name, int(count)))

    for items in groups.values():
        if len(items) < 2 or sum(count for _, count in items) < 5:
            continue
        items.sort(key=lambda item: (-item[1], -len(item[0]), item[0]))
        canonical = items[0][0]
        for name, count in items[1:]:
            alias[name] = canonical
            method[name] = "auto_en"
            rows[name] = count

    alias = {key: resolve(value, alias) for key, value in alias.items()}
    alias_df = pd.DataFrame([
        {"alias": key, "canonical": value, "method": method.get(key, "manual"),
         "rows": rows.get(key, 0)}
        for key, value in alias.items() if key != value
    ])
    pending_df = pd.DataFrame([
        {"alias": key, "canonical": key, "method": "pending_review",
         "rows": int(counts[key])}
        for key in PENDING_REVIEW if key in counts.index
    ])
    alias_df = pd.concat([alias_df, pending_df], ignore_index=True)
    alias_df = alias_df.sort_values(["rows", "alias"], ascending=[False, True],
                                    ignore_index=True)

    co = cooperation.copy()
    co["a2"] = co["app_a"].astype(str).map(lambda x: resolve(x, alias))
    co["b2"] = co["app_b"].astype(str).map(lambda x: resolve(x, alias))
    dropped_self = int((co["a2"] == co["b2"]).sum())
    co = co[co["a2"] != co["b2"]].copy()
    co["lo"] = co[["a2", "b2"]].min(axis=1)
    co["hi"] = co[["a2", "b2"]].max(axis=1)
    merged = (co.groupby(["lo", "hi"], as_index=False)
                .agg(weight=("weight", "sum"), raw_pairs=("weight", "size"))
                .rename(columns={"lo": "app_a", "hi": "app_b"})
                .sort_values(["weight", "app_a", "app_b"],
                             ascending=[False, True, True], ignore_index=True))
    merged["app_a"] = merged["app_a"].astype("string")
    merged["app_b"] = merged["app_b"].astype("string")
    merged["weight"] = merged["weight"].astype("int64")
    merged["raw_pairs"] = merged["raw_pairs"].astype("int64")

    mapped = applicants.copy()
    mapped["canonical"] = mapped["applicant_std"].astype(str).map(lambda x: resolve(x, alias))
    per_patent = mapped[["patent_id", "canonical"]].drop_duplicates()
    patent_counts = per_patent.groupby("canonical").size().reset_index(name="patent_count")
    applicant_rows = mapped.groupby("canonical").size().reset_index(name="applicant_rows")
    alias_counts = (alias_df[alias_df["method"] != "pending_review"]
                    .groupby("canonical").size().reset_index(name="alias_count"))
    company_counts = (patent_counts.merge(applicant_rows, on="canonical", how="left")
                      .merge(alias_counts, on="canonical", how="left"))
    company_counts["alias_count"] = company_counts["alias_count"].fillna(0).astype(int)
    total_patents = int(per_patent["patent_id"].nunique())
    company_counts["share_pct"] = (100 * company_counts["patent_count"] / total_patents
                                   ).round(3)
    company_counts = company_counts.sort_values(
        ["patent_count", "canonical"], ascending=[False, True], ignore_index=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    alias_path = OUT_DIR / "company_alias.csv"
    merged_path = OUT_DIR / "cooperation_merged.parquet"
    counts_path = OUT_DIR / "company_patent_counts.csv"
    alias_df.to_csv(alias_path, index=False, encoding="utf-8-sig")
    merged.to_parquet(merged_path, index=False)
    company_counts.to_csv(counts_path, index=False, encoding="utf-8-sig")

    covered_rows = int(alias_df.loc[alias_df["method"] != "pending_review", "rows"].sum())
    alias_names = set(alias_df.loc[alias_df["method"] != "pending_review", "alias"])
    covered_patents = int(mapped[
        mapped["applicant_std"].astype(str).isin(alias_names)
    ]["patent_id"].nunique())
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "alias_rows": len(alias_df),
        "manual_aliases": int((alias_df["method"] == "manual").sum()),
        "auto_ascii_aliases": int((alias_df["method"] == "auto_en").sum()),
        "pending_review": int((alias_df["method"] == "pending_review").sum()),
        "covered_applicant_rows": covered_rows,
        "covered_patents": covered_patents,
        "cooperation_raw_edges": len(cooperation),
        "cooperation_merged_edges": len(merged),
        "dropped_self_loops": dropped_self,
        "companies_after_merge": len(company_counts),
        "top_companies": [
            {"company": row.canonical, "patents": int(row.patent_count)}
            for row in company_counts.head(15).itertuples()
        ],
        "top_cooperation": [
            {"app_a": row.app_a, "app_b": row.app_b, "weight": int(row.weight)}
            for row in merged.head(10).itertuples()
        ],
        "missing_manual_keys": sorted(missing_manual),
        "notes": ["Kia and Hyundai are separate canonical groups.",
                  "中国南方 is pending_review and not merged.",
                  "Contract applicants/cooperation tables are unchanged."],
    }
    (OUT_DIR / "alias_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    for path in (alias_path, merged_path, counts_path):
        shutil.copy2(path, DELIVERY_DIR / path.name)
    (DELIVERY_DIR / "alias_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    top_aliases = "\n".join(
        f"| {r.alias} | {r.canonical} | {r.method} | {r.rows:,} |"
        for r in alias_df.head(25).itertuples()
    )
    top_pairs = "\n".join(
        f"| {r.app_a} ↔ {r.app_b} | {r.weight:,} |" for r in merged.head(15).itertuples()
    )
    readme = f"""# P1-8 企业别名合并（展示层）

生成时间：{summary['generated_at']}

> 这是**展示层**结果，不改契约表 `applicants.parquet` / `cooperation.parquet` / 图谱节点名。
> 别名表是可扩展的 Top 名单，不是完整实体消解。

## 文件

| 文件 | 内容 |
|---|---|
| `company_alias.csv` | `alias, canonical, method, rows`；method = manual / auto_en / pending_review |
| `cooperation_merged.parquet` | 合并后的合作边，`weight` 相加，自环已删，额外保留 `raw_pairs` |
| `company_patent_counts.csv` | 按 canonical 去重专利数、申请关系行数、合并别名数、占比 |
| `alias_summary.json` | 覆盖率、Top 企业、Top 合作对、缺失人工键 |

## 规则

- **manual**：Top 名单人工映射，处理中英文重复、Incopat 截断名和明确集团级名称。
- **auto_en**：只对纯英文名做大小写/标点/法律后缀归一（Corp/Corporation、Co., Ltd. 等），不跨语言自动合并。
- 中文名不自动去后缀，避免把不同子公司误并；截断名（`比亚迪司`、`雅马哈株`）走人工表。
- **Kia 与 Hyundai 不合并**：Kia → `起亚`，Hyundai Motor → `现代公司`。
- **`中国南方` 标 `pending_review`，不硬并**：174 行中大部分原始申请人为重庆长安新能源，其余可能误并，需抽样核对。
- `理工大学2` 这类泛化名、`Hyundai Wia/Autron/Transys` 等零部件子公司不合并。

## 规模

- 别名条目：{len(alias_df):,}（manual {summary['manual_aliases']:,}、auto_en {summary['auto_ascii_aliases']:,}、pending_review {summary['pending_review']:,}）
- 覆盖申请关系行：{covered_rows:,}
- 覆盖专利：{covered_patents:,}
- 合作边：{len(cooperation):,} → {len(merged):,}（自环删除 {dropped_self:,}）
- 合并后企业：{len(company_counts):,}

## Top 别名

| alias | canonical | method | rows |
|---|---|---|---:|
{top_aliases}

## Top 合作对（合并后）

| 主体对 | 共同专利数 |
|---|---:|
{top_pairs}

## 局限

- 不是完整实体消解；未列入的名称保持原样。
- 集团级合并会隐藏子公司差异；需要子公司级分析时使用原始 `applicants.parquet`。
- `中国南方` 仍是独立节点，合作网络里可能出现 `中国南方 ↔ 重庆长安`，解读时要标“待核”。
"""
    (DELIVERY_DIR / "说明.md").write_text(readme, encoding="utf-8")

    print(json.dumps({
        "aliases": len(alias_df), "merged_pairs": len(merged),
        "dropped_self": dropped_self, "companies": len(company_counts),
        "covered_patents": covered_patents,
        "missing_manual": len(missing_manual),
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
