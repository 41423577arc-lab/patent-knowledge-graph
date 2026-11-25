"""P3: shared filters and simple aggregation; P1 owns network algorithms."""
from core.data_loader import load_result, load_table


def overview_data(years=None, country=None, domain=None):
    tables = {name: load_table(name) for name in ["patents", "applicants", "patent_ipc", "patent_topic", "patent_efficacy"]}
    patents = tables["patents"]
    patents = patents.loc[patents["is_in_sample"].fillna(False)]
    if years:
        patents = patents.loc[patents["apply_year"].between(*years)]
    if country:
        patents = patents.loc[patents["country"].isin(country)]
    if domain:
        ids = tables["patent_topic"].loc[tables["patent_topic"]["domain"].isin(domain), "patent_id"]
        patents = patents.loc[patents["patent_id"].isin(ids)]
    ids = set(patents["patent_id"])
    technical = patents.loc[~patents["patent_type"].fillna("").str.contains("外观", regex=False)]
    tech_ids = set(technical["patent_id"])
    related = {name: table.loc[table["patent_id"].isin(ids)] for name, table in tables.items() if name != "patents"}
    annual = patents.loc[patents["apply_year"].between(2010, 2023)].groupby("apply_year").size().reset_index(name="count")
    topic = related["patent_topic"].loc[related["patent_topic"]["patent_id"].isin(tech_ids)]
    return {"patents": patents, "technical": technical, "tables": related, "topics": topic,
            "patent_count": len(ids), "applicant_count": related["applicants"]["applicant_std"].nunique(),
            "ipc_count": related["patent_ipc"]["ipc_code"].nunique(), "annual": annual}


def distribution(data, dimension):
    if dimension == "专利类型":
        frame, field = data["patents"], "patent_type"
    elif dimension == "公开国别":
        frame, field = data["patents"], "country"
    else:
        name, field = ("patent_ipc", "ipc_code") if dimension == "IPC" else ("patent_efficacy", "efficacy_l1")
        frame = data["tables"][name]
        frame = frame.loc[frame["patent_id"].isin(set(data["technical"]["patent_id"]))]
    return frame.dropna(subset=[field]).groupby(field)["patent_id"].nunique().sort_values(ascending=False).head(15).reset_index(name="count")


def applicant_metrics(top_n=10, query="", metric="patent_count"):
    applicants = load_table("applicants")
    patents = load_table("patents")
    base = applicants.loc[applicants["patent_id"].isin(patents["patent_id"])]
    counts = base.groupby("applicant_std")["patent_id"].nunique().reset_index(name="patent_count")
    note = "申请量由当前基础表去重统计；主体尚未做展示层别名合并。"
    try:
        result = load_result("company_metrics")
        expected = result.attrs["metrics_manifest"]["source_rows"]
        from core.data_loader import TABLE_COLUMNS
        if any(expected.get(name) != len(load_table(name)) for name in TABLE_COLUMNS):
            raise ValueError("Precomputed metrics belong to another dataset")
        counts = result
        note = "网络指标仅限当前研究数据的样本内引用网络，不能称全产业影响力。"
    except (FileNotFoundError, ValueError, KeyError):
        note += " 预计算网络指标缺失或与当前数据不匹配，暂不展示旧指标。"
    if query:
        counts = counts.loc[counts["applicant_std"].str.contains(query, case=False, regex=False, na=False)]
    actual_metric = metric if metric in counts else "patent_count"
    result = counts.sort_values([actual_metric, "applicant_std"], ascending=[False, True]).head(top_n).copy()
    result.attrs["note"] = note
    return result


def cooperation_for(name):
    frame = load_table("cooperation")
    return frame.loc[frame["app_a"].eq(name) | frame["app_b"].eq(name)].sort_values("weight", ascending=False).head(30)


def topic_year():
    data = overview_data()
    return data["topics"].merge(data["patents"][["patent_id", "apply_year"]], on="patent_id").dropna(subset=["apply_year"]).groupby(["topic", "domain", "apply_year"])["patent_id"].nunique().reset_index(name="count").rename(columns={"apply_year": "year"})
