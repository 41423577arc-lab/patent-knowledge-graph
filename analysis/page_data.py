"""P3: page data through P1's loaders; no file paths, drivers or network metrics."""
from core.data_loader import load_result, load_table


def overview_data() -> dict:
    patents = load_table("patents")
    patents = patents.loc[patents["is_in_sample"].fillna(False)]
    ids = set(patents["patent_id"])
    applicants = load_table("applicants")
    ipc = load_table("patent_ipc")
    annual = patents.dropna(subset=["apply_year"]).groupby("apply_year").size().reset_index(name="count")
    return {
        "patents": patents,
        "patent_count": len(ids),
        "applicant_count": applicants.loc[applicants["patent_id"].isin(ids), "applicant_std"].nunique(),
        "ipc_count": ipc.loc[ipc["patent_id"].isin(ids), "ipc_code"].nunique(),
        "annual": annual,
    }


def applicant_metrics(top_n: int = 10):
    table = load_result("company_metrics")
    return table.sort_values(["patent_count", "applicant_std"], ascending=[False, True]).head(top_n)


def topic_year():
    return load_result("topic_year")
