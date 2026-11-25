"""P1-8 H1: company-level citation aggregation (口径 C).

For each sample patent, take its normalized applicants as the citing companies
and ``representatives.cited_applicants`` as the set of external cited companies.
One citing patent contributes at most once to a (citing, cited) pair.

This is NOT an exact patent-level edge: ``cited_applicants`` is a flat list for
all cited patents of the citing patent.  All outputs are display/analysis
helpers; contract ``citations.parquet`` is unchanged.
"""
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime

import pandas as pd

from core import config

APPLICANTS = config.PROCESSED_DIR / "applicants.parquet"
REPS = config.RESULTS_DIR / "representatives.parquet"
ALIAS = config.RESULTS_DIR / "company_alias.csv"
OUT_DIR = config.RESULTS_DIR
DELIVERY_DIR = config.ROOT_DIR / "交付给同伴的内容" / "P1-8_质量与别名"

SPLIT_RE = re.compile(r"[;；|]")

# Additional cited-side variants.  The applicant-side alias table does not cover
# every name that only appears in 被引证申请人, so keep a focused group map here.
CITED_MANUAL = {
    "Hyundai Motor Company": "现代公司",
    "Hyundai Motor Co Ltd": "现代公司",
    "现代自动车株式会社": "现代公司",
    "Kia Motors Corporation": "起亚",
    "Kia Corporation": "起亚",
    "起亚自动车株式会社": "起亚",
    "Toyota Jidosha Kabushiki Kaisha": "丰田公司",
    "Toyota Motor Corp": "丰田公司",
    "丰田自动车株式会社": "丰田公司",
    "Toyota Motor Engineering & Manufacturing North America, Inc.": "丰田公司",
    "Honda Motor Co., Ltd.": "本田公司",
    "Honda Motor Co Ltd": "本田公司",
    "本田技研工业株式会社": "本田公司",
    "Nissan Motor Co., Ltd.": "日产公司",
    "Nissan Motor": "日产公司",
    "Ford Global Technologies, Llc": "福特汽车",
    "福特全球技术公司": "福特汽车",
    "国家电网有限公司": "国家电网",
    "国家电网公司": "国家电网",
    "国网北京市电力公司": "国家电网",
    "中国第一汽车股份有限公司": "中国一汽",
    "一汽解放汽车有限公司": "中国一汽",
    "比亚迪股份有限公司": "比亚迪",
    "Byd Company Limited": "比亚迪",
    "浙江吉利控股集团有限公司": "吉利汽车",
    "吉利汽车研究院(宁波)有限公司": "吉利汽车",
    "北京新能源汽车股份有限公司": "北汽集团",
    "北汽福田汽车股份有限公司": "北汽集团",
    "重庆长安汽车股份有限公司": "重庆长安",
    "重庆长安新能源汽车科技有限公司": "重庆长安",
    "东风汽车集团股份有限公司": "东风汽车",
    "东风汽车集团有限公司": "东风汽车",
    "东风商用车有限公司": "东风汽车",
    "东风柳州汽车有限公司": "东风汽车",
    "长城汽车股份有限公司": "长城汽车",
    "奥动新能源汽车科技有限公司": "奥动新能源",
    "安徽江淮汽车集团股份有限公司": "江淮汽车",
    "奇瑞汽车股份有限公司": "奇瑞汽车",
    "奇瑞新能源汽车股份有限公司": "奇瑞汽车",
    "奇瑞商用车(安徽)有限公司": "奇瑞汽车",
    "潍柴动力股份有限公司": "潍柴动力",
    "珠海格力电器股份有限公司": "格力集团",
    "宁德时代新能源科技股份有限公司": "宁德时代",
    "Contemporary Amperex Technology Co., Limited": "宁德时代",
    "广州汽车集团股份有限公司": "广汽集团",
    "上海汽车集团股份有限公司": "上汽集团",
    "广州小鹏汽车科技有限公司": "小鹏汽车",
    "郑州宇通客车股份有限公司": "宇通客车",
    "江铃汽车股份有限公司": "江铃汽车",
    "Bayerische Motoren Werke Aktiengesellschaft": "宝马公司",
    "Dr. Ing. H.C. F. Porsche Aktiengesellschaft": "保时捷",
    "Audi Ag": "奥迪",
    "Gm Global Technology Operations Llc": "通用汽车",
    "Lg Chem, Ltd.": "LG化学",
    "Lg Energy Solution, Ltd.": "LG新能源",
    "Robert Bosch Gmbh": "博世公司",
    "Denso Corp": "电装公司",
    "Denso Corporation": "电装公司",
    "Samsung Sdi Co., Ltd.": "三星SDI",
    "Samsung Electronics Co., Ltd.": "三星电子",
    "株式会社村田制作所": "村田",
    "Volkswagen Aktiengesellschaft": "大众公司",
    "Psa Automobiles Sa": "标致公司",
    "Toshiba Corp": "东芝公司",
    "Huawei Technologies Co., Ltd.": "华为公司",
    "华为数字能源技术有限公司": "华为公司",
}

LEGAL_SUFFIXES = [
    "corporation", "corp", "company", "co", "ltd", "limited", "inc",
    "gmbh", "ag", "plc", "holdings", "group", "kabushiki", "kaisha",
]


def is_ascii(name: str) -> bool:
    return all(ord(ch) < 128 for ch in name)


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


def clean_name(value: str) -> str:
    value = str(value).strip().strip("[]")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"-[A-Za-z]$", "", value)  # Incopat -C/-U/-R/-G suffix
    return value.strip()


def split_names(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [clean_name(part) for part in SPLIT_RE.split(str(value)) if clean_name(part)]


def main():
    applicants = pd.read_parquet(APPLICANTS)
    reps = pd.read_parquet(REPS)
    alias_df = pd.read_csv(ALIAS)
    alias = dict(zip(alias_df["alias"].astype(str), alias_df["canonical"].astype(str)))

    en_norm = {}
    for key, canonical in {**CITED_MANUAL}.items():
        if is_ascii(key):
            en_norm[norm_en(key)] = canonical
    for key, canonical in alias.items():
        if is_ascii(key):
            en_norm.setdefault(norm_en(key), canonical)

    def resolve_cited(name: str) -> str:
        name = alias.get(name, name)
        name = CITED_MANUAL.get(name, name)
        if is_ascii(name):
            name = en_norm.get(norm_en(name), name)
        return name

    citing_by_patent = (applicants.groupby("patent_id")["applicant_std"]
                        .agg(lambda values: sorted(set(str(v) for v in values))))

    pairs = defaultdict(set)
    citing_patents_with_cited_company = 0
    self_edges = 0
    citing_rows = 0

    for row in reps[["patent_id", "cited_applicants"]].itertuples(index=False):
        if pd.isna(row.cited_applicants):
            continue
        citing_rows += 1
        citing_companies = [alias.get(name, name)
                            for name in citing_by_patent.get(row.patent_id, [])]
        if not citing_companies:
            continue
        cited_companies = []
        for name in split_names(row.cited_applicants):
            name = resolve_cited(name)
            if name:
                cited_companies.append(name)
        cited_companies = sorted(set(cited_companies))
        if not cited_companies:
            continue
        citing_patents_with_cited_company += 1
        for citing in citing_companies:
            for cited in cited_companies:
                if citing == cited:
                    self_edges += 1
                    continue
                pairs[(citing, cited)].add(row.patent_id)

    records = [
        {"citing_company": citing, "cited_company": cited, "citing_patent_count": len(ids)}
        for (citing, cited), ids in pairs.items()
    ]
    result = pd.DataFrame(records, columns=["citing_company", "cited_company",
                                            "citing_patent_count"])
    result = result.sort_values(
        ["citing_patent_count", "citing_company", "cited_company"],
        ascending=[False, True, True], ignore_index=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "company_citation_pairs.parquet"
    result.to_parquet(out_path, index=False)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "data/results/representatives.parquet::cited_applicants",
        "patents_total": len(reps),
        "patents_with_cited_applicants": int(reps["cited_applicants"].notna().sum()),
        "patents_used_for_pairs": citing_patents_with_cited_company,
        "pairs": len(result),
        "unique_citing_companies": int(result["citing_company"].nunique()) if len(result) else 0,
        "unique_cited_companies": int(result["cited_company"].nunique()) if len(result) else 0,
        "pair_patent_links": int(result["citing_patent_count"].sum()) if len(result) else 0,
        "self_links_dropped": self_edges,
        "alias_rows": len(alias_df),
        "top_pairs": [
            {"citing_company": row.citing_company, "cited_company": row.cited_company,
             "citing_patent_count": int(row.citing_patent_count)}
            for row in result.head(15).itertuples()
        ],
        "notes": [
            "One citing patent contributes at most once to a (citing, cited) pair.",
            "cited_applicants is a flat list across all cited patents; this is an aggregate, not an exact edge.",
            "Self pairs are dropped.",
            "Company names use company_alias.csv when an alias exists; contract tables are unchanged.",
            "cited_applicants does not distinguish company/university/individual; the table is subject-level, despite the company_ prefix.",
        ],
    }
    (OUT_DIR / "company_citation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_path, DELIVERY_DIR / out_path.name)
    (DELIVERY_DIR / "company_citation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    top_lines = "\n".join(
        f"| {row.citing_company} → {row.cited_company} | {row.citing_patent_count:,} |"
        for row in result.head(20).itertuples()
    )
    readme = f"""# P1-8 企业级引用聚合（口径 C）

生成时间：{summary['generated_at']}

> 这是**聚合辅助表**，不改契约 `citations.parquet`。它回答“某企业的专利引用集合里出现过哪些企业”，不是精确的专利引用边。

## 字段

| 字段 | 含义 |
|---|---|
| `citing_company` | 引用方企业（样例内专利的标准化申请人） |
| `cited_company` | 被引方企业（`cited_applicants` 拆分后，经别名归一） |
| `citing_patent_count` | 该引用方企业有多少件专利引用过该被引方企业；同一件专利对同一企业只计一次 |

## 覆盖

- 专利总数：{len(reps):,}
- `cited_applicants` 非空：{summary['patents_with_cited_applicants']:,}
- 可形成企业对的引用专利：{summary['patents_used_for_pairs']:,}
- 企业对：{summary['pairs']:,}
- 涉及引用方企业：{summary['unique_citing_companies']:,}；被引方企业：{summary['unique_cited_companies']:,}
- 专利-企业对计数合计：{summary['pair_patent_links']:,}
- 自引用对删除：{summary['self_links_dropped']:,}

## Top 企业对

| 企业对 | 引用专利数 |
|---|---:|
{top_lines}

## 口径与局限

- 一件引用专利可能引用多家企业；`cited_applicants` 是这些被引专利申请人平铺后的列表，无法还原“某件被引专利对应哪家企业”。
- 同一件专利对同一被引企业只计一次，避免同一企业多个被引专利重复放大。
- 企业名用 `company_alias.csv` 归一；`中国南方` 仍是 `pending_review`，未硬并。
- `cited_applicants` 不区分企业/高校/个人，表名虽为 `company_`，实际是**主体级**；P3 若只展示企业，需要按类型再过滤。
- 只能说明“引用集合里出现过”，不能当作精确技术依赖边；所有结论要标“基于 X 件引用专利 / Y 个主体”。
"""
    (DELIVERY_DIR / "说明_企业级引用.md").write_text(readme, encoding="utf-8")

    print(json.dumps({
        "pairs": len(result),
        "patents_used": citing_patents_with_cited_company,
        "citing_companies": summary["unique_citing_companies"],
        "cited_companies": summary["unique_cited_companies"],
        "links": summary["pair_patent_links"],
        "self_dropped": self_edges,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
