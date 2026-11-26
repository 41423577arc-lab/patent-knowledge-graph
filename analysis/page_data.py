"""P3: shared filters and simple aggregation; P1 owns network algorithms."""
import hashlib
import math
import pandas as pd
import streamlit as st
from core import config
from core.data_loader import TABLE_COLUMNS, load_result, load_table


def data_token():
    root = config.DATA_DIR / "_sample" if config.USE_SAMPLE else config.PROCESSED_DIR
    results = root / "results" if config.USE_SAMPLE else config.RESULTS_DIR
    paths = [root / f"{name}.parquet" for name in TABLE_COLUMNS]
    paths += [results / "metrics_manifest.json", results / "company_metrics.parquet", results / "topic_year.parquet"]
    # Metadata only: all table contents are still loaded through the frozen loader.
    return (config.USE_SAMPLE, str(root), str(results), tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (str(p), None, None) for p in paths))


@st.cache_data(ttl=60, max_entries=2, show_spinner=False)
def _snapshot(token):
    tables = {name: load_table(name) for name in TABLE_COLUMNS}
    results, notes, source_digests = {}, {}, None
    for name in ["company_metrics", "topic_year"]:
        try:
            candidate = load_result(name)
            manifest = candidate.attrs["metrics_manifest"]
            if any(manifest.get("source_rows", {}).get(n) != len(t) for n,t in tables.items()):
                raise ValueError("预计算来源行数与当前七表不一致")
            expected = manifest.get("source_table_sha256", {})
            if not all(n in expected for n in tables):
                raise ValueError("清单缺少源表内容签名，无法可靠确认同规模数据的版本")
            if source_digests is None:
                source_digests = {n: hashlib.sha256(t.to_json(orient="split", index=False, date_format="iso", force_ascii=False).encode("utf-8")).hexdigest() for n,t in tables.items()}
            if any(source_digests[n] != expected[n] for n in tables):
                raise ValueError("预计算来源内容与当前七表不一致")
            if name == "company_metrics" and not set(candidate["applicant_std"]) <= set(tables["applicants"]["applicant_std"]):
                raise ValueError("指标主体名与契约主体名不一致，需先交付稳定的别名映射接口")
            results[name] = candidate
            notes[name] = "来源范围与版本已校验；固定研究数据范围，不随页面筛选重算。"
        except (FileNotFoundError, ValueError, KeyError) as exc:
            results[name] = None
            notes[name] = "预计算结果或清单尚未交付" if isinstance(exc, FileNotFoundError) else "预计算清单结构不完整" if isinstance(exc, KeyError) else str(exc)
    return {"tables": tables, "metrics": results["company_metrics"], "topic_year": results["topic_year"], "metric_note": notes["company_metrics"], "result_notes": notes, "token": token}


def dataset():
    return _snapshot(data_token())


def source_tables(bundle=None):
    return (bundle or dataset())["tables"]


def overview_data(years=None, country=None, domain=None, bundle=None):
    tables = source_tables(bundle)
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
    related = {name: tables[name].loc[tables[name]["patent_id"].isin(ids)] for name in ["applicants", "patent_ipc", "patent_topic", "patent_efficacy"]}
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


METRIC_LABELS = {"patent_count":"专利申请量", "cited_count":"样本内被引次数", "pagerank":"PageRank 影响力", "degree":"度中心性", "betweenness":"中介中心性"}
METRIC_HELP = {"patent_count":"按主体关联的不同专利编号计数；共同申请分别计入各主体。", "cited_count":"当前样本内引用边的被引次数，非全产业引用。", "pagerank":"引用网络中的结构影响力，由 P1 预计算。", "degree":"网络邻接程度，具体归一化口径由 P1 清单确定。", "betweenness":"位于网络最短路径之间的程度，由 P1 计算，可能为抽样近似。"}


def metric_available(bundle, metric):
    if metric == "patent_count": return True
    table=bundle["metrics"]
    if table is None or metric not in table: return False
    values=pd.to_numeric(table[metric],errors="coerce").dropna()
    return bool(values.map(math.isfinite).any())


def ranking(bundle, query="", metric="patent_count", top_n=20):
    tables = bundle["tables"]
    if metric == "patent_count":
        applicants = tables["applicants"]
        ids = set(tables["patents"].loc[tables["patents"]["is_in_sample"].fillna(False),"patent_id"])
        frame = applicants.loc[applicants["patent_id"].isin(ids)].groupby("applicant_std")["patent_id"].nunique().reset_index(name=metric)
    elif not metric_available(bundle, metric):
        return pd.DataFrame(columns=["applicant_std",metric])
    else:
        frame = bundle["metrics"].copy()
        frame[metric]=pd.to_numeric(frame[metric],errors="coerce")
        frame=frame.loc[frame[metric].notna() & frame[metric].fillna(0).map(math.isfinite)]
    if query: frame = frame.loc[frame["applicant_std"].str.contains(query,case=False,regex=False,na=False)]
    return frame.sort_values([metric,"applicant_std"],ascending=[False,True]).head(top_n)


def applicant_metrics(top_n=10, query="", metric="patent_count"):
    bundle=dataset(); frame=ranking(bundle,query,metric,top_n)
    frame.attrs["note"]=bundle["metric_note"]
    return frame


def cooperation_for(name, bundle=None):
    frame = source_tables(bundle)["cooperation"]
    return frame.loc[frame["app_a"].eq(name) | frame["app_b"].eq(name)].sort_values("weight", ascending=False).head(30)


def topic_year():
    bundle = dataset()
    if bundle["topic_year"] is not None: return bundle["topic_year"]
    data = overview_data(bundle=bundle)
    return data["topics"].merge(data["patents"][["patent_id", "apply_year"]], on="patent_id").dropna(subset=["apply_year"]).groupby(["topic", "domain", "apply_year"])["patent_id"].nunique().reset_index(name="count").rename(columns={"apply_year": "year"})


def patent_selection(bundle, patents=None, query="", topic=None, domain=None, applicant=None):
    tables=source_tables(bundle)
    frame=tables["patents"] if patents is None else patents
    frame=frame.loc[frame["is_in_sample"].fillna(False)]
    if applicant:
        ids=tables["applicants"].loc[tables["applicants"]["applicant_std"].eq(applicant),"patent_id"]
        frame=frame.loc[frame["patent_id"].isin(ids)]
    topics=tables["patent_topic"]
    if topic: topics=topics.loc[topics["topic"].eq(topic)]
    if domain: topics=topics.loc[topics["domain"].eq(domain)]
    if topic or domain: frame=frame.loc[frame["patent_id"].isin(topics["patent_id"])]
    if query:
        mask=frame["title"].fillna("").str.contains(query,case=False,regex=False)|frame["patent_id"].fillna("").str.contains(query,case=False,regex=False)
        frame=frame.loc[mask]
    return frame.sort_values("patent_id")


def page_slice(frame, page=1, size=20):
    pages=max(1,math.ceil(len(frame)/size)); page=max(1,min(int(page),pages))
    return frame.iloc[(page-1)*size:page*size],page,pages


def patent_detail(bundle, patent_id):
    tables=source_tables(bundle); rows=tables["patents"].loc[tables["patents"]["patent_id"].eq(patent_id)]
    return {"patent": None if rows.empty else rows.iloc[0].to_dict(), **{name:tables[name].loc[tables[name]["patent_id"].eq(patent_id)] for name in ["applicants","patent_ipc","patent_topic"]}}


def shared_patents(bundle, first, second):
    table=source_tables(bundle)["applicants"]
    a=set(table.loc[table["applicant_std"].eq(first),"patent_id"])
    b=set(table.loc[table["applicant_std"].eq(second),"patent_id"])
    patents=source_tables(bundle)["patents"]
    return patents.loc[patents["patent_id"].isin(a & b)].sort_values("patent_id")
