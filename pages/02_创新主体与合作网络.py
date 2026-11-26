"""P3: discover subjects, inspect portfolios and verify cooperation evidence."""
import streamlit as st
import plotly.express as px
from analysis.page_data import dataset,ranking,metric_available,METRIC_LABELS,METRIC_HELP,patent_selection,overview_data,distribution,cooperation_for,shared_patents
from ui.theme import apply_theme
from ui.components import page_header,chart
from ui.evidence import patent_browser,qa_link,scope_notice
from ui.qa_visuals import graph_figure
def open_partner(name):
    st.session_state["org_query"]=""
    st.session_state["org_selected"]=name

apply_theme("创新主体与合作网络")
page_header("02 创新主体与合作网络","从创新主体发现，进入技术布局、合作关系和专利证据。")
scope_notice()
try:
    bundle=dataset()
    with st.container(border=True):
        st.subheader("创新主体发现与排名")
        a,b,c=st.columns([3,2,1])
        query=a.text_input("检索创新主体名称",key="org_query")
        metric=b.selectbox("排名指标",list(METRIC_LABELS),format_func=lambda k:METRIC_LABELS[k]+("（不可用）" if not metric_available(bundle,k) else ""))
        top_n=c.selectbox("前 N 位",[10,20,50])
        st.caption(METRIC_HELP[metric])
        ranked=ranking(bundle,query,metric,top_n)
        if not metric_available(bundle,metric):
            st.warning("此指标不可用："+bundle["metric_note"]+"。没有用申请量替代所选指标。")
        elif ranked.empty: st.info("没有匹配主体。")
        else:
            chart(px.bar(ranked,x="applicant_std",y=metric,labels={"applicant_std":"创新主体",metric:METRIC_LABELS[metric]}))
            st.dataframe(ranked.rename(columns={"applicant_std":"创新主体",**METRIC_LABELS}),hide_index=True,width="stretch")
        names=sorted(bundle["tables"]["applicants"]["applicant_std"].dropna().unique())
        if query: names=[n for n in names if query.casefold() in n.casefold()]
        if not names: st.info("请调整检索条件以选择主体。")
        else:
            previous=st.session_state.get("org_selected")
            preferred=[previous] if previous in names else []
            ordered=list(dict.fromkeys([*preferred,*ranked["applicant_std"].tolist(),*names]))[:200]
            st.caption(f"匹配 {len(names):,} 个主体；选择器最多列出 200 个，可用名称检索缩小范围，排名仍基于全部匹配记录。")
            name=st.selectbox("选择排行榜主体 / 检索到的主体",ordered,key="org_selected")
    if names:
        patents=patent_selection(bundle,applicant=name)
        with st.container(border=True):
            st.subheader("主体技术布局与专利证据")
            st.write("创新主体：",name)
            types=bundle["tables"]["applicants"].loc[bundle["tables"]["applicants"]["applicant_std"].eq(name),"applicant_type"].fillna("未知").replace("","未知").unique()
            st.write("主体类型：", "、".join(map(str,types)))
            st.caption(f"当前研究数据中 {len(patents):,} 件专利；主体名未合并别名。不提供无依据的企业简介或经营评分。")
            qa_link(f"创新主体「{name}」的技术布局和代表性专利有哪些？","org_ask")
            ids=set(patents["patent_id"])
            profile={"tables":{n:t.loc[t["patent_id"].isin(ids)] for n,t in bundle["tables"].items() if "patent_id" in t},"patents":patents,"technical":patents.loc[~patents["patent_type"].fillna("").str.contains("外观",regex=False)]}
            annual,ipc,topics,evidence=st.tabs(["年度申请","IPC 布局","主题与领域","专利详情"])
            with annual:
                frame=patents.loc[patents["apply_year"].between(2010,2023)].groupby("apply_year").size().reset_index(name="count")
                st.caption("全部关联专利 · 2010—2023 完整年度窗口；缺失年份不补零。")
                if not frame.empty: chart(px.line(frame,x="apply_year",y="count",markers=True))
                else: st.info("无完整年度记录。")
            with ipc:
                counts=distribution(profile,"IPC")
                st.caption("非外观设计技术类专利；主副 IPC 均按实际关系展示前 15 类。")
                if not counts.empty: chart(px.bar(counts,x="ipc_code",y="count"))
                else: st.info("未提供 IPC。")
            with topics:
                table=profile["tables"]["patent_topic"]
                table=table.loc[table["patent_id"].isin(profile["technical"]["patent_id"])]
                counts=table.groupby(["topic","domain"])["patent_id"].nunique().reset_index(name="专利数")
                st.dataframe(counts.rename(columns={"topic":"技术主题","domain":"技术领域"}),hide_index=True,width="stretch")
            with evidence: patent_browser(bundle,patents,key="org_patents")
        with st.container(border=True):
            st.subheader("共同申请网络与证据下钻")
            links=cooperation_for(name,bundle)
            st.caption("契约主体名，未做别名合并。仅绘该主体权重最高的前 30 条共同申请边；不是完整网络，也不是引用关系。")
            if links.empty: st.info("当前主体没有共同申请边。")
            else:
                partners=sorted((set(links["app_a"])|set(links["app_b"]))-{name})
                graph={"nodes":[{"id":n,"label":n,"type":"Applicant"} for n in [name,*partners]],"edges":[{"source":r.app_a,"target":r.app_b,"type":"CO_APPLIED_WITH","weight":int(r.weight)} for r in links.itertuples()]}
                figure,_=graph_figure(graph)
                if figure is not None: chart(figure)
                partner=st.selectbox("选择合作主体 / 合作边",partners,key="org_partner")
                selected=links.loc[(links["app_a"].eq(name)&links["app_b"].eq(partner))|(links["app_b"].eq(name)&links["app_a"].eq(partner))]
                st.button("查看该合作主体的技术布局",on_click=open_partner,args=(partner,))
                shared=shared_patents(bundle,name,partner)
                weight=selected["weight"].sum()
                st.write(f"{name} ↔ {partner}：契约边权 {weight:,}；当前可核验共同专利 {len(shared):,} 件。")
                if int(weight)!=len(shared): st.warning("边权与当前可见专利交集不一致，可能涉及样例截取或数据范围差异；不将边权冒充可展示证据数量。")
                qa_link(f"「{name}」和「{partner}」共同申请了哪些专利，涉及哪些技术？","org_coop_ask")
                patent_browser(bundle,shared,key="org_shared")
except (FileNotFoundError,ValueError) as exc: st.error(str(exc))
