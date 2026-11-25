"""P3: current-data rankings and cooperation drilldown; no centrality recomputation."""
import streamlit as st
import plotly.express as px
from analysis.page_data import applicant_metrics, cooperation_for
from ui.theme import apply_theme
from ui.components import page_header,section,chart,data_table,empty_state,error_state
from ui.qa_visuals import graph_figure
apply_theme("创新主体与合作网络")
page_header("02 创新主体与合作网络", "合作为共同申请关系；引用指标仅限样本内网络。")
a,b,c=st.columns([3,1,2])
query=a.text_input("创新主体检索")
top_n=b.selectbox("展示数量",[10,20,50])
metric=c.selectbox("排序指标",["patent_count","cited_count","pagerank","degree","betweenness"])
try:
    metrics=applicant_metrics(top_n,query,metric)
    st.info(metrics.attrs["note"])
    actual=metric if metric in metrics else "patent_count"
    if metric not in metrics: st.warning("所选网络指标尚不可用，当前展示真实申请量。")
    section("创新主体排名 · 当前数据范围")
    if metrics.empty: empty_state("没有匹配主体。")
    else:
        chart(px.bar(metrics,x="applicant_std",y=actual))
        data_table(metrics)
        name=st.selectbox("主体合作下钻",metrics["applicant_std"].tolist())
        links=cooperation_for(name)
        section("共同申请网络 · 契约主体名，未做展示层别名合并")
        st.caption("边权是共同申请专利数。当前只读合作契约表；不把引用关系或待核别名当成已确认合作。")
        if links.empty: empty_state("当前主体没有返回共同申请边。")
        else:
            names=sorted(set(links["app_a"])|set(links["app_b"]))
            graph={"nodes":[{"id":n,"label":n,"type":"Applicant"} for n in names],"edges":[{"source":r.app_a,"target":r.app_b,"type":"CO_APPLIED_WITH","weight":int(r.weight)} for r in links.itertuples()]}
            figure,notes=graph_figure(graph)
            if figure is not None: chart(figure)
            data_table(links)
except (FileNotFoundError,ValueError) as exc: error_state(str(exc))
