"""P3: discovery, technical distributions and paginated patent evidence."""
import streamlit as st
import plotly.express as px
from analysis.page_data import dataset,overview_data,distribution
from ui.theme import apply_theme
from ui.components import page_header,metric_row,chart
from ui.evidence import patent_browser,qa_link,scope_notice
apply_theme("产业技术全景")
page_header("01 产业技术全景","在一致筛选范围内，从技术分布追溯到专利证据。")
scope_notice()
def reset():
    for key in list(st.session_state):
        if key.startswith("ov_"): del st.session_state[key]
try:
    bundle=dataset(); initial={"patents":bundle["tables"]["patents"],"topics":bundle["tables"]["patent_topic"]}
    with st.container(border=True):
        st.subheader("产业概况")
        a,b,c,d=st.columns([2,2,2,1])
        years=sorted(initial["patents"]["apply_year"].dropna().astype(int).unique())
        selected=a.slider("申请年份",min(years),max(years),(min(years),max(years)),key="ov_years") if len(years)>1 else None
        countries=b.multiselect("公开国别",sorted(initial["patents"]["country"].dropna().unique()),key="ov_countries")
        domains=c.multiselect("技术领域",sorted(initial["topics"]["domain"].dropna().unique()),key="ov_domains")
        d.button("重置筛选",on_click=reset)
        year_filter=None if not selected or selected==(min(years),max(years)) else selected
        data=overview_data(year_filter,countries,domains,bundle)
        st.caption(f"当前范围：{year_filter or '全部年份（含缺失年份）'} · {', '.join(countries) or '全部公开国别'} · {', '.join(domains) or '全部领域'}；公开国别不是申请人国别。")
        metric_row([("全部专利",data["patent_count"]),("技术类专利",len(data["technical"])),("创新主体（未合并）",data["applicant_count"])])
    with st.container(border=True):
        st.subheader("技术发展与分布")
        trend,dist,topics=st.tabs(["年度趋势","专利与技术分布","技术主题下钻"])
        with trend:
            st.caption("当前筛选全部专利，趋势只绘 2010—2023；2024—2025 不完整。")
            if data["annual"].empty: st.info("缺少完整年份数据。")
            else: chart(px.line(data["annual"],x="apply_year",y="count",markers=True))
        with dist:
            dimension=st.radio("分布维度",["专利类型","公开国别","IPC","技术功效"],horizontal=True,key="ov_dimension")
            counts=distribution(data,dimension)
            st.caption("IPC/功效以非外观设计技术类为分母；其他以全部专利为分母。同件专利可归多类。展示前 15 类。")
            if counts.empty: st.info("暂无对应分布。")
            else: chart(px.bar(counts,x=counts.columns[0],y="count"))
        with topics:
            topic_names=sorted(data["topics"]["topic"].dropna().unique())
            topic=st.selectbox("选择技术主题",[None,*topic_names],format_func=lambda x:x or "全部主题",key="ov_topic")
            rows=data["topics"]
            ranking=rows.groupby("topic")["patent_id"].nunique().sort_values(ascending=False).head(20).reset_index(name="count")
            st.caption("当前技术类范围内前 20 个规则抽取主题；“未细分”保留名称，不当作标准细粒度分类。")
            if not ranking.empty: chart(px.bar(ranking,x="count",y="topic",orientation="h"))
            if topic: qa_link(f"技术主题「{topic}」的主要创新主体和代表性专利有哪些？","ov_topic_ask")
    with st.container(border=True):
        st.subheader("专利证据与详情")
        st.caption("沿用上面的年份、国别、领域及所选技术主题。")
        patent_browser(bundle,data["patents"],key="ov_patents",topic=topic)
except (FileNotFoundError,ValueError) as exc: st.error(str(exc))
