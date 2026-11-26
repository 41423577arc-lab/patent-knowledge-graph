"""P3: shared filters and simple aggregation; P1 owns network algorithms."""
import hashlib
import math
from copy import deepcopy
import pandas as pd
import streamlit as st
from core import config
from core.data_loader import TABLE_COLUMNS, load_result, load_table
from analysis.subjects import load_index
from analysis.membership import member_of


def data_token():
    root = config.DATA_DIR / "_sample" if config.USE_SAMPLE else config.PROCESSED_DIR
    results = root / "results" if config.USE_SAMPLE else config.RESULTS_DIR
    paths = [root / f"{name}.parquet" for name in TABLE_COLUMNS]
    paths += [results / "metrics_manifest.json", results / "company_metrics.parquet", results / "topic_year.parquet"]
    paths += [config.RESULTS_DIR/"company_alias.csv",config.DATA_DIR.parent/"source_manifest.json"]
    if not config.USE_SAMPLE:
        paths += [config.RESULTS_DIR/"company_patent_counts.csv",config.RESULTS_DIR/"cooperation_merged.parquet"]
    versions=[]
    for path in [results/"metrics_manifest.json",config.DATA_DIR.parent/"source_manifest.json"]:
        try:versions.append((str(path),hashlib.sha256(path.read_bytes()).hexdigest()))
        except OSError as exc:versions.append((str(path),type(exc).__name__))
    # Only small version manifests are hashed on a hit; tables use the frozen loader.
    return (config.USE_SAMPLE, str(root), str(results), tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (str(p), None, None) for p in paths),tuple(versions))


def _build_snapshot(token):
    tables = {name: load_table(name) for name in TABLE_COLUMNS}
    results, notes, source_digests = {}, {}, None
    source_manifest={}
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
                source_digests = {n: _source_digest(t,expected[n]) for n,t in tables.items()}
            if any(source_digests[n] != expected[n] for n in tables):
                raise ValueError("预计算来源内容与当前七表不一致")
            if name == "company_metrics" and not set(candidate["applicant_std"]) <= set(tables["applicants"]["applicant_std"]):
                raise ValueError("指标主体名与契约主体名不一致，需先交付稳定的别名映射接口")
            results[name] = candidate
            source_manifest=manifest
            notes[name] = "来源范围与版本已校验；固定研究数据范围，不随页面筛选重算。"
        except (OSError, ValueError, KeyError) as exc:
            results[name] = None
            notes[name] = "预计算结果或清单尚未交付" if isinstance(exc, FileNotFoundError) else "预计算清单结构不完整" if isinstance(exc, KeyError) else str(exc)
    subjects=load_index(tables,source_manifest)
    return {"tables": tables, "metrics": results["company_metrics"], "topic_year": results["topic_year"], "metric_note": notes["company_metrics"], "result_notes": notes, "token": token,"subjects":subjects}


def _source_digest(table,expected):
    options={"orient":"split","index":False,"date_format":"iso","force_ascii":False}
    # Materialize scalar columns once instead of iterating Arrow scalars for every JSON row.
    fast=hashlib.sha256(table.astype(object).to_json(**options).encode("utf-8")).hexdigest()
    if fast==expected:return fast
    # Preserve the original validation contract for unusual scalar/dtype representations.
    return hashlib.sha256(table.to_json(**options).encode("utf-8")).hexdigest()


@st.cache_resource(ttl=600,max_entries=2,show_spinner="正在加载并校验当前研究数据…")
def _resource_snapshot(token):
    return _build_snapshot(token)


@st.cache_data(ttl=600,max_entries=2,show_spinner="正在加载并校验当前研究数据…")
def _copied_snapshot(token):
    return _build_snapshot(token)


def _cow_available():
    # pandas 3 guarantees CoW. Do not change the global option used by P1/P2.
    return int(pd.__version__.split(".")[0])>=3


def _snapshot(token):
    if not _cow_available():
        copied=_copied_snapshot(token)
        if copied["metrics"] is None or copied["topic_year"] is None:_copied_snapshot.clear(token)
        return copied
    source=_resource_snapshot(token)
    if source["metrics"] is None or source["topic_year"] is None:_resource_snapshot.clear(token)
    view={**source,"tables":{n:t.copy(deep=False) for n,t in source["tables"].items()},
          "result_notes":dict(source["result_notes"])}
    for name in ["metrics","topic_year"]:
        view[name]=None if source[name] is None else source[name].copy(deep=False)
    view["subjects"]={k:v.copy(deep=False) if isinstance(v,pd.DataFrame) else dict(v) if isinstance(v,dict) else v.copy() if isinstance(v,set)
                      else deepcopy(v) if isinstance(v,list) else v for k,v in source["subjects"].items()}
    return view


def _clear_snapshot():
    _resource_snapshot.clear();_copied_snapshot.clear()


_snapshot.clear=_clear_snapshot


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
        patents = patents.loc[member_of(patents["country"],country)]
    if domain:
        ids = tables["patent_topic"].loc[member_of(tables["patent_topic"]["domain"],domain), "patent_id"]
        patents = patents.loc[member_of(patents["patent_id"],ids)]
    ids = set(patents["patent_id"])
    technical = patents.loc[~patents["patent_type"].fillna("").str.contains("外观", regex=False)]
    tech_ids = set(technical["patent_id"])
    related = {name: tables[name].loc[member_of(tables[name]["patent_id"],ids)] for name in ["applicants", "patent_ipc", "patent_topic", "patent_efficacy"]}
    annual = patents.loc[patents["apply_year"].between(2010, 2023)].groupby("apply_year").size().reset_index(name="count")
    topic = related["patent_topic"].loc[member_of(related["patent_topic"]["patent_id"],tech_ids)]
    if domain: topic=topic.loc[member_of(topic["domain"],domain)]
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
        frame = frame.loc[member_of(frame["patent_id"],set(data["technical"]["patent_id"]))]
    return frame.dropna(subset=[field]).groupby(field)["patent_id"].nunique().sort_values(ascending=False).head(15).reset_index(name="count")


METRIC_LABELS = {"patent_count":"专利申请量", "cited_count":"研究范围内被引次数", "pagerank":"PageRank 影响力", "degree":"度中心性", "betweenness":"中介中心性"}
METRIC_HELP = {"patent_count":"按所选主体集合关联的不同专利编号计数；共同申请分别计入各主体。", "cited_count":"P1 原始主体在研究数据内部引证网络中的去重被引边数，非全产业引用。", "pagerank":"研究数据内部引证网络的原始主体结构影响力，由 P1 预计算。", "degree":"P1 原始主体引证网络转无向后的归一化邻接程度；不是共同申请网络。", "betweenness":"P1 原始主体有向引证网络的归一化最短路径中介程度；全量为采样近似，口径以清单为准。"}


def metric_available(bundle, metric):
    if metric == "patent_count": return True
    table=bundle["metrics"]
    if table is None or metric not in table: return False
    values=pd.to_numeric(table[metric],errors="coerce").dropna()
    return bool(values.map(math.isfinite).any())


def ranking(bundle, query="", metric="patent_count", top_n=20, *, merged=False):
    tables = bundle["tables"]
    if merged and metric!="patent_count":
        raise ValueError("网络指标仅支持 P1 原始主体口径，不能合并或相加")
    if metric == "patent_count":
        if merged:
            if not bundle.get("subjects",{}).get("available"): raise ValueError("确认别名展示不可用")
            frame=bundle["subjects"]["counts"]
        else:
            applicants = tables["applicants"]
            ids = set(tables["patents"].loc[tables["patents"]["is_in_sample"].fillna(False),"patent_id"])
            frame = applicants.loc[member_of(applicants["patent_id"],ids)].groupby("applicant_std")["patent_id"].nunique().reset_index(name=metric)
    elif not metric_available(bundle, metric):
        return pd.DataFrame(columns=["applicant_std",metric])
    else:
        frame = bundle["metrics"].copy()
        frame[metric]=pd.to_numeric(frame[metric],errors="coerce")
        frame=frame.loc[frame[metric].notna() & frame[metric].fillna(0).map(math.isfinite)]
    if query:
        names=subject_names(bundle,query,merged=merged)
        frame=frame.loc[member_of(frame["applicant_std"],names)]
    return frame.sort_values([metric,"applicant_std"],ascending=[False,True]).head(top_n)


def applicant_metrics(top_n=10, query="", metric="patent_count"):
    bundle=dataset(); frame=ranking(bundle,query,metric,top_n)
    frame.attrs["note"]=bundle["metric_note"]
    return frame


def cooperation_for(name, bundle=None, *, merged=False):
    bundle=bundle or dataset()
    frame = bundle["subjects"]["cooperation"] if merged else source_tables(bundle)["cooperation"]
    return frame.loc[frame["app_a"].eq(name) | frame["app_b"].eq(name)].sort_values("weight", ascending=False).head(30)


def topic_year():
    bundle = dataset()
    if bundle["topic_year"] is not None: return bundle["topic_year"]
    data = overview_data(bundle=bundle)
    return data["topics"].merge(data["patents"][["patent_id", "apply_year"]], on="patent_id").dropna(subset=["apply_year"]).groupby(["topic", "domain", "apply_year"])["patent_id"].nunique().reset_index(name="count").rename(columns={"apply_year": "year"})


def topic_history(bundle, data, topic, years=None, countries=None, domains=None):
    """Precomputed whole-scope counts, or an exact basic aggregation after filtering."""
    start,end=years or (2010,2023)
    start,end=max(2010,start),min(2023,end)
    empty=pd.DataFrame(columns=["year","count"])
    if start>end: return empty,"所选年份不包含 2010—2023 完整年度窗口。"
    precomputed=bundle.get("topic_year")
    if precomputed is not None and not countries:
        rows=precomputed.loc[precomputed["topic"].eq(topic)]
        if domains: rows=rows.loc[member_of(rows["domain"],domains)]
        rows=rows.loc[rows["year"].between(start,end),["year","count"]]
        if not rows.empty and not rows["year"].duplicated().any():
            return rows.sort_values("year"),"P1 已校验主题年度表；按申请年统计，年度窗口及领域与当前筛选一致。仅 2010—2023 完整年度，未记录年份保持缺失。"
    topics=data["topics"].loc[data["topics"]["topic"].eq(topic),["patent_id"]].drop_duplicates()
    rows=topics.merge(data["technical"][["patent_id","apply_year"]],on="patent_id")
    rows=rows.loc[rows["apply_year"].between(start,end)]
    return rows.groupby("apply_year")["patent_id"].nunique().reset_index(name="count").rename(columns={"apply_year":"year"}),"按申请年统计当前年份、公开国别、领域筛选后的技术类专利；仅 2010—2023 完整年度，按 patent_id 去重，未记录年份保持缺失。"


def topic_patents(data,topic):
    """Match topic and domain on the same association row, not independent IDs."""
    if not topic:return data["patents"]
    ids=set(data["topics"].loc[data["topics"]["topic"].eq(topic),"patent_id"])
    return data["patents"].loc[member_of(data["patents"]["patent_id"],ids)]


def topic_subjects(bundle,data,topic,*,merged=False):
    """Applicant counts within the selected technical topic and visible scope."""
    ids=set(topic_patents(data,topic)["patent_id"])
    owners=bundle["tables"]["applicants"].loc[lambda t:member_of(t["patent_id"],ids),["applicant_std","patent_id"]].copy()
    if merged:
        index=bundle["subjects"]
        mapping=index["trace"].set_index("applicant_std")["canonical"].to_dict()
        owners["applicant_std"]=owners["applicant_std"].map(lambda n:mapping.get(n,n))
    return owners.groupby("applicant_std")["patent_id"].nunique().reset_index(name="patent_count").sort_values(["patent_count","applicant_std"],ascending=[False,True])


def representative_patents(bundle,patents,limit=10):
    """P3 evidence ordering only: internal recorded citations, then application year."""
    visible=set(bundle["tables"]["patents"].loc[lambda t:t["is_in_sample"].fillna(False),"patent_id"])
    edges=bundle["tables"]["citations"].loc[lambda t:member_of(t["citing_id"],visible)&member_of(t["cited_id"],visible)]
    counts=edges.drop_duplicates(["citing_id","cited_id"]).groupby("cited_id").size()
    ranked=patents.drop_duplicates("patent_id").copy()
    ranked["cited_count"]=ranked["patent_id"].map(counts).fillna(0).astype(int)
    return ranked.sort_values(["cited_count","apply_year","patent_id"],ascending=[False,False,True]).head(limit)


def cooperation_summary(bundle,name,*,merged=False):
    edges=cooperation_for(name,bundle,merged=merged)
    index=bundle.get("subjects",{})
    groups=index.get("patents" if merged else "raw_patents") if index.get("available") else None
    rows=[]
    for edge in edges.itertuples():
        partner=edge.app_b if edge.app_a==name else edge.app_a
        count=len(groups.get(name,frozenset())&groups.get(partner,frozenset())) if groups is not None else len(shared_patents(bundle,name,partner,merged=merged))
        rows.append({"app_a":name,"app_b":partner,"weight":int(edge.weight),
                     "p1_weight":int(getattr(edge,"p1_weight",edge.weight)),
                     "shared_count":count})
    return pd.DataFrame(rows,columns=["app_a","app_b","weight","p1_weight","shared_count"])


def patent_selection(bundle, patents=None, query="", topic=None, domain=None, applicant=None, *, merged=False):
    tables=source_tables(bundle)
    frame=tables["patents"] if patents is None else patents
    frame=frame.loc[frame["is_in_sample"].fillna(False)]
    if applicant:
        members=subject_members(bundle,applicant,merged=merged)
        ids=tables["applicants"].loc[member_of(tables["applicants"]["applicant_std"],members),"patent_id"]
        frame=frame.loc[member_of(frame["patent_id"],ids)]
    topics=tables["patent_topic"]
    if topic: topics=topics.loc[topics["topic"].eq(topic)]
    if domain: topics=topics.loc[topics["domain"].eq(domain)]
    if topic or domain: frame=frame.loc[member_of(frame["patent_id"],topics["patent_id"])]
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


def patent_citation_stats(bundle, patent_id):
    """Count recorded directed patent pairs; never reconstruct edges from raw lists."""
    tables=source_tables(bundle)
    visible=set(tables["patents"].loc[tables["patents"]["is_in_sample"].fillna(False),"patent_id"])
    if patent_id not in visible:
        raise ValueError("专利不在当前研究范围内")
    edges=tables["citations"]
    incoming=edges.loc[edges["cited_id"].eq(patent_id) & member_of(edges["citing_id"],visible)]
    outgoing=edges.loc[edges["citing_id"].eq(patent_id)]
    return {"cited_count":len(incoming.drop_duplicates(["citing_id","cited_id"])),
            "citing_count":outgoing["cited_id"].nunique(),
            "external_citing_count":outgoing.loc[~member_of(outgoing["cited_id"],visible),"cited_id"].nunique()}


def subject_members(bundle, name, *, merged=False):
    if not merged: return (name,)
    index=bundle.get("subjects",{})
    if not index.get("available"): raise ValueError("确认别名展示不可用")
    return index["members"].get(name,())


def subject_names(bundle, query="", *, merged=False):
    if merged:
        index=bundle["subjects"]
        if not index.get("available"): return []
        names=sorted(index["members"])
        if query:
            text=query.casefold()
            names=[n for n in names if text in n.casefold() or any(text in raw.casefold() for raw in index["members"][n])]
    else:
        names=sorted(bundle["tables"]["applicants"]["applicant_std"].dropna().unique())
        if query: names=[n for n in names if query.casefold() in n.casefold()]
    return names


def shared_patents(bundle, first, second, *, merged=False):
    table=source_tables(bundle)["applicants"]
    a=set(table.loc[member_of(table["applicant_std"],subject_members(bundle,first,merged=merged)),"patent_id"])
    b=set(table.loc[member_of(table["applicant_std"],subject_members(bundle,second,merged=merged)),"patent_id"])
    patents=source_tables(bundle)["patents"]
    return patents.loc[patents["is_in_sample"].fillna(False) & member_of(patents["patent_id"],a & b)].sort_values("patent_id")
