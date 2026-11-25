"""P3: real-data overview with one shared filter scope."""
import streamlit as st
import plotly.express as px
from analysis.page_data import overview_data, distribution
from ui.theme import apply_theme
from ui.components import page_header, metric_row, section, chart, data_table, empty_state, error_state
apply_theme("产业技术全景")
page_header("01 产业技术全景", "全部专利与技术类口径分开；2024—2025 数据不完整，不作趋势结论。")
try:
    initial = overview_data()
    a,b,c = st.columns(3)
    years = sorted(initial["patents"]["apply_year"].dropna().astype(int).unique())
    selected_years = a.slider("申请年份范围", min(years), max(years), (min(years), max(years))) if len(years)>1 else None
    countries = b.multiselect("公开国别（不是申请人国别）", sorted(initial["patents"]["country"].dropna().unique()))
    domains = c.multiselect("技术领域", sorted(initial["topics"]["domain"].dropna().unique()))
    data = overview_data(selected_years, countries, domains)
    metric_row([("全部专利", data["patent_count"]), ("技术类专利",len(data["technical"])), ("创新主体（未合并）",data["applicant_count"])])
    section("年度申请量 · 当前筛选全部专利 · 2010—2023")
    if data["annual"].empty: empty_state("筛选范围内没有可靠完整年份记录。")
    else: chart(px.line(data["annual"],x="apply_year",y="count",markers=True))
    dimension = st.radio("分布维度", ["专利类型","公开国别","IPC","技术功效"], horizontal=True)
    counts = distribution(data, dimension)
    st.caption("IPC / 功效按非外观设计技术类专利计数；同件专利可归属多类，各类数量不可直接相加。其他图按全部专利计数。")
    if counts.empty: empty_state()
    else: chart(px.bar(counts,x=counts.columns[0],y="count"))
    section("技术主题 · 当前筛选技术类专利")
    topics = data["topics"].groupby(["topic","domain"])["patent_id"].nunique().reset_index(name="count").sort_values("count",ascending=False)
    st.caption("规则抽取主题不是标准分类；含“未细分”的主题单列在明细中，不据此推断技术成熟度。")
    data_table(topics)
    section("筛选后的专利明细")
    st.dataframe(data["patents"],hide_index=True,width="stretch")
except (FileNotFoundError,ValueError) as exc: error_state(str(exc))
