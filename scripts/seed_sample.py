"""Create a reproducible real-data subset without inventing missing fields."""
import json
from itertools import combinations

import pandas as pd

from core.config import DATA_DIR
from core.data_loader import TABLE_COLUMNS


def main():
    source = DATA_DIR / "legacy"
    target = DATA_DIR / "_sample"
    target.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(source / "patents.csv", dtype=str, keep_default_na=False).head(150)
    ids = set(old["id"])
    patents = pd.DataFrame({"patent_id": old["id"], "title": old["title"]})
    for column in TABLE_COLUMNS["patents"][2:]:
        patents[column] = None
    # Legacy date is a mixture of publication/application/priority dates.
    # Neither application date nor publication date can be recovered reliably.
    patents["apply_year"] = pd.Series([None] * len(old), dtype="Int64")
    patents["country"] = old["id"].str.extract(r"^([A-Z]{2})", expand=False)
    patents["legal_status"] = old["legal"]
    patents["is_in_sample"] = True
    applicants = pd.read_csv(source / "rel_applied.csv", dtype=str).drop_duplicates()
    all_applicants = applicants.copy()
    applicants = applicants[applicants["patent_id"].isin(ids)].rename(columns={"company": "applicant_std"})
    applicants["applicant_raw"] = None  # Original forms/order were lost in the old export.
    applicants["applicant_type"] = None
    applicants["is_first"] = pd.Series(pd.NA, index=applicants.index, dtype="boolean")
    ipc = old.loc[old["ipc_main"].ne(""), ["id", "ipc_main"]].rename(
        columns={"id": "patent_id", "ipc_main": "ipc_code"})
    ipc["is_main"] = True
    cites = pd.read_csv(source / "rel_cites.csv", dtype=str).rename(
        columns={"citing": "citing_id", "cited": "cited_id"})
    cites = cites[cites["citing_id"].isin(ids)].drop(columns=["cited_is_stub"])
    cites["cited_in_sample"] = cites["cited_id"].isin(ids)
    # Only provide an attribution when the old export identifies one applicant.
    groups = all_applicants.groupby("patent_id")["company"].agg(list)
    unambiguous = {pid: names[0] for pid, names in groups.items() if len(names) == 1}
    cites["cited_applicant_std"] = cites["cited_id"].map(unambiguous)
    pairs = []
    for names in applicants.groupby("patent_id")["applicant_std"]:
        pairs.extend(combinations(sorted(set(names[1])), 2))
    cooperation = pd.DataFrame(pairs, columns=["app_a", "app_b"])
    cooperation = cooperation.groupby(["app_a", "app_b"]).size().reset_index(name="weight")
    tables = {
        "patents": patents, "applicants": applicants, "patent_ipc": ipc,
        "citations": cites, "cooperation": cooperation,
        "patent_topic": pd.DataFrame(columns=TABLE_COLUMNS["patent_topic"]),
        "patent_efficacy": pd.DataFrame(columns=TABLE_COLUMNS["patent_efficacy"]),
    }
    for name, table in tables.items():
        table[TABLE_COLUMNS[name]].to_parquet(target / f"{name}.parquet", index=False)
    from scripts.calculate_metrics import write_results
    write_results(tables, target / "results", "sample")
    (target / "manifest.json").write_text(json.dumps({
        "source": "data/legacy/*.csv", "kind": "development_subset",
        "patents": len(patents), "selection": "first 150 rows of legacy patents.csv",
        "missing_fields": ["abstract", "apply_date", "apply_year", "pub_date", "patent_type",
                           "applicant_raw", "applicant_type", "is_first"],
        "empty_tables": ["patent_topic", "patent_efficacy"],
        "note": "Not a representative statistical sample. Full extraction is P1's task.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({name: len(table) for name, table in tables.items()})


if __name__ == "__main__":
    main()
