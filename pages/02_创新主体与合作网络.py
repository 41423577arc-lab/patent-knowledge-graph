"""P3: discover subjects, inspect portfolios and verify cooperation evidence."""
import streamlit as st
import plotly.express as px
from analysis.page_data import dataset,ranking,metric_available,METRIC_LABELS,METRIC_HELP,patent_selection,distribution,cooperation_for,shared_patents,subject_names,subject_members,representative_patents,cooperation_summary
from ui.theme import apply_theme
from ui.components import page_header,chart,data_problem
from ui.evidence import patent_browser,question_link,scope_notice
from ui.questions import OPERATIONS,SUBJECT_ACTIONS
from ui.navigation import restore_source,SUBJECTS,return_link
from ui.exports import summary_download
from ui.selection import selected_rank_name
from analysis.membership import member_of
from ui.qa_visuals import graph_figure
from ui.theme import PLOTLY_TEMPLATE
def open_partner(name):
    st.session_state["org_query"]=""
    st.session_state["org_selected"]=name

apply_theme("创新主体与合作网络")
page_header("02 创新主体与合作网络","从创新主体发现，进入技术布局、合作关系和专利证据。")
scope_notice()
restore_source(SUBJECTS)
origin=st.session_state.get("org_overview_origin")
if origin:
    st.caption("来自主题分析。当前主体详情采用完整研究数据范围；可返回全景页继续原筛选。")
    return_link(origin,key="org_return_overview")
try:
    pending=st.session_state.pop("org_pending_partner",None)
    if pending: open_partner(pending)
    bundle=dataset()
    with st.container(border=True):
        st.subheader("创新主体发现与排名")
        a,b,c=st.columns([3,2,1])
        query=a.text_input("检索创新主体名称",key="org_query")
        metric=b.selectbox("排名指标",list(METRIC_LABELS),format_func=lambda k:METRIC_LABELS[k]+("（不可用）" if not metric_available(bundle,k) else ""),key="org_metric")
        top_n=c.selectbox("前 N 位",[10,20,50],key="org_top_n")
        index=bundle["subjects"]
        scope=st.radio("主体申请量与详情口径",["confirmed","raw"],key="org_scope",horizontal=True,
                       format_func=lambda k:"已确认别名合并（专利去重）" if k=="confirmed" else "原始标准化主体",
                       disabled=metric!="patent_count" or not index.get("available"))
        merged=scope=="confirmed" and metric=="patent_count" and index.get("available",False)
        scope_label="已确认别名合并（专利去重）" if merged else "原始标准化主体"
        if not index.get("available"): st.warning(index["note"])
        if metric!="patent_count":
            st.info("本指标及下方详情固定使用 P1 原始标准化主体；被引次数和中心性属于研究数据内部引证网络，不是共同申请网络。不合并或相加网络指标。")
        elif merged:
            st.caption(index["note"]+(" P1 合并申请量表已与当前专利集合逐主体核对一致。" if not index["count_differences"] and not index["sample"] else "当前范围重新对专利集合去重，不使用全量辅助表数量。"))
            if index["count_differences"]: st.warning("P1 合并申请量与当前映射的集合存在差异，页面只展示当前集合去重结果，原辅助表不修改。")
        st.caption(METRIC_HELP[metric])
        ranked=ranking(bundle,query,metric,top_n,merged=merged)
        if not metric_available(bundle,metric):
            st.warning("此指标不可用："+bundle["metric_note"]+"。没有用申请量替代所选指标。")
        elif ranked.empty: st.info("没有匹配主体。")
        else:
            figure=px.bar(ranked,x="applicant_std",y=metric,custom_data=["applicant_std"],labels={"applicant_std":"创新主体",metric:METRIC_LABELS[metric]})
            figure.update_layout(template=PLOTLY_TEMPLATE,clickmode="event+select")
            # New query/scope renders a new chart so stale selected points cannot retarget a subject.
            rank_key=f"org_rank_plot_{metric}_{scope}_{query}_{top_n}"
            picked=st.plotly_chart(figure,width="stretch",theme=None,key=rank_key,on_select="rerun",selection_mode="points")
            clicked=selected_rank_name(picked,ranked["applicant_std"].tolist())
            signature=(rank_key,clicked)
            if clicked and signature!=st.session_state.get("org_rank_plot_selection"):
                st.session_state["org_selected"]=clicked
            st.session_state["org_rank_plot_selection"]=signature
            event=st.dataframe(ranked.rename(columns={"applicant_std":"创新主体",**METRIC_LABELS}),hide_index=True,width="stretch",
                               on_select="rerun",selection_mode="single-row",key="org_rank_table")
            signature=(tuple(ranked["applicant_std"]),tuple(event.selection.rows))
            if event.selection.rows and 0<=event.selection.rows[0]<len(ranked) and signature!=st.session_state.get("org_rank_selection"):
                st.session_state["org_selected"]=ranked.iloc[event.selection.rows[0]]["applicant_std"]
            st.session_state["org_rank_selection"]=signature
            st.caption("点击柱形或勾选表格左侧的行选择框，可查看主体技术布局；若图表点击不可用，请用表格选择或下拉框。")
            exported=ranked.copy()
            if merged:
                exported=exported.rename(columns={"applicant_std":"canonical"})
                exported["raw_members"]=exported["canonical"].map(lambda n:"；".join(index["members"][n]))
            summary_download(exported,"导出当前排行榜",key="applicant_ranking",context=f"当前检索={query or '全部'}；前{top_n}；{scope_label}；{METRIC_LABELS[metric]}；{METRIC_HELP[metric]}")
        names=subject_names(bundle,query,merged=merged)
        if not names: st.info("请调整检索条件以选择主体。")
        else:
            previous=st.session_state.get("org_selected")
            preferred=[previous] if previous in names else []
            ordered=list(dict.fromkeys([*preferred,*ranked["applicant_std"].tolist(),*names]))[:200]
            st.caption(f"匹配 {len(names):,} 个主体；选择器最多列出 200 个，可用名称检索缩小范围，排名仍基于全部匹配记录。")
            name=st.selectbox("选择排行榜主体 / 检索到的主体",ordered,key="org_selected")
    if names:
        members=subject_members(bundle,name,merged=merged)
        patents=patent_selection(bundle,applicant=name,merged=merged)
        ids=set(patents["patent_id"])
        with st.container(border=True):
            st.subheader("主体技术布局与专利证据")
            st.write("创新主体：",name)
            types=bundle["tables"]["applicants"].loc[member_of(bundle["tables"]["applicants"]["applicant_std"],members)&member_of(bundle["tables"]["applicants"]["patent_id"],ids),"applicant_type"].fillna("未知").replace("","未知").unique()
            st.write("主体类型：", "、".join(map(str,types)))
            st.caption(f"{scope_label} · 当前研究范围内 {len(patents):,} 件去重专利；所有布局和专利明细均使用同一主体集合。")
            with st.expander(f"所含原始标准化主体（{len(members)} 个）"):
                st.write(list(members))
                st.caption("来自 P1 原始 applicant_std；申请人原文仍可在专利详情中追溯。")
            pending_names=set(members)&index.get("pending",set())
            if pending_names: st.warning("名称待确认："+"、".join(sorted(pending_names))+"；保持原名，未进行别名合并。")
            actions=("topics",*[k for k in SUBJECT_ACTIONS if k!="topics"])
            action=st.selectbox("继续问答的内容",actions,format_func=lambda k:OPERATIONS[k][1],key="org_qa_action")
            st.caption("合并模式复用 P2 的确认映射及原始主体集合。P2 全局榜单/网络指标仍按原始主体；合作表累加权重可能与去重证据不同，须按来源解读。")
            caution=" 名称待确认，P3 跳过对应合并合作边；P2 若返回原始记录，不代表名称或合作结论已确认。" if pending_names else ""
            question_link(action,name,"org_ask",source_page=SUBJECTS,context=f"来自主体页：「{name}」，口径：{scope_label}；所含原始名：{'、'.join(members)}；当前专利集合去重 {len(patents)} 件。原名模式下问答仍可能展开确认别名，合并模式使用与 P2 相同的主体集合。"+caution)
            profile={"tables":{n:t.loc[member_of(t["patent_id"],ids)] for n,t in bundle["tables"].items() if "patent_id" in t},"patents":patents,"technical":patents.loc[~patents["patent_type"].fillna("").str.contains("外观",regex=False)]}
            annual,ipc,topics,evidence=st.tabs(["年度申请","IPC 布局","主题与领域","代表专利与明细"])
            with annual:
                frame=patents.loc[patents["apply_year"].between(2010,2023)].groupby("apply_year").size().reset_index(name="count")
                st.caption("全部关联专利按申请年（非公开年）统计 · 2010—2023 完整年度窗口；缺失年份不补零。")
                if not frame.empty: chart(px.line(frame,x="apply_year",y="count",markers=True))
                else: st.info("无完整年度记录。")
            with ipc:
                counts=distribution(profile,"IPC")
                st.caption("非外观设计技术类专利；主副 IPC 均按实际关系展示前 15 类。")
                if not counts.empty: chart(px.bar(counts,x="ipc_code",y="count"))
                else: st.info("未提供 IPC。")
                summary_download(counts,"导出当前主体 IPC 分布",key="subject_ipc",context=f"主体={name}；{scope_label}；非外观设计技术类；主副IPC；前15类，按专利去重")
            with topics:
                table=profile["tables"]["patent_topic"]
                table=table.loc[member_of(table["patent_id"],profile["technical"]["patent_id"])]
                counts=table.groupby(["topic","domain"])["patent_id"].nunique().reset_index(name="专利数")
                st.dataframe(counts.rename(columns={"topic":"技术主题","domain":"技术领域"}),hide_index=True,width="stretch")
                summary_download(counts,"导出当前主体主题分布",key="subject_topics",context=f"主体={name}；{scope_label}；非外观设计技术类；每主题/领域按专利去重")
            with evidence:
                view=st.radio("专利证据范围",["代表性专利前10件","全部关联专利"],horizontal=True,key="org_evidence_view")
                st.caption("代表专利仅按研究范围内去重被引次数、申请年、编号排序，无额外评分；不等同价值评价。明细不开放批量下载。")
                evidence_patents=representative_patents(bundle,patents) if view=="代表性专利前10件" else patents
                patent_browser(bundle,evidence_patents,key="org_patents")
        with st.container(border=True):
            st.subheader("共同申请网络与证据下钻")
            links=cooperation_for(name,bundle,merged=merged)
            st.caption(f"{scope_label}。仅绘该主体权重最高的前 30 条共同申请边，不是完整网络或引用关系。合并图按当前共同专利交集去重，保留 P1 累加权重对照。")
            if merged:
                skipped=[r for r in index["skipped_edges"] if name in (r["app_a"],r["app_b"])]
                if skipped: st.warning(f"已跳过 {len(skipped)} 条待核或无法证明一致的合并合作边；可切换原始标准化主体模式查看契约记录。")
            elif not links.empty:
                uncertain=(set(links["app_a"])|set(links["app_b"]))&index.get("pending",set())
                if uncertain: st.warning("原始契约记录含待核名称："+"、".join(sorted(uncertain))+"；仅作原始记录追溯，不作为已确认的别名或合作结论。")
            if links.empty: st.info("当前主体没有共同申请边。")
            else:
                with st.expander("合作关系汇总与导出"):
                    summary=cooperation_summary(bundle,name,merged=merged)
                    st.dataframe(summary.rename(columns={"app_a":"主体","app_b":"合作主体","weight":"展示边权","p1_weight":"P1边权","shared_count":"去重共同专利数"}),hide_index=True,width="stretch")
                    summary_download(summary,"导出当前合作关系汇总",key="cooperation_summary",context=f"主体={name}；{scope_label}；当前展示前30条共同申请边；weight为展示边权，p1_weight为P1原始或累加权重，shared_count为当前研究范围去重证据数；不是引用网络")
                partners=sorted((set(links["app_a"])|set(links["app_b"]))-{name})
                graph={"nodes":[{"id":n,"label":n,"type":"Applicant"} for n in [name,*partners]],"edges":[{"source":r.app_a,"target":r.app_b,"type":"CO_APPLIED_WITH","weight":int(r.weight)} for r in links.itertuples()]}
                figure,_=graph_figure(graph)
                if figure is not None:
                    figure.update_layout(template=PLOTLY_TEMPLATE)
                    picked=st.plotly_chart(figure,width="stretch",theme=None,key="org_network",on_select="rerun",selection_mode="points")
                    points=picked.selection.points
                    custom=points[-1].get("customdata",[]) if points else []
                    signature=(name,tuple(custom))
                    if len(custom)>=2 and signature!=st.session_state.get("org_network_selection"):
                        st.session_state["org_network_selection"]=signature
                        if custom[0]=="node" and custom[1] in partners:
                            st.session_state["org_pending_partner"]=custom[1]; st.rerun()
                        elif custom[0]=="edge" and str(custom[1]).isdigit():
                            edge_index=int(custom[1])
                            if edge_index<len(links):
                                edge=links.iloc[edge_index]
                                st.session_state["org_partner"]=edge["app_b"] if edge["app_a"]==name else edge["app_a"]
                    st.caption("点击合作节点可查看其技术布局；点击边上的关系标记可选择该合作边，下方保留下拉选择。")
                partner=st.selectbox("选择合作主体 / 合作边",partners,key="org_partner")
                selected=links.loc[(links["app_a"].eq(name)&links["app_b"].eq(partner))|(links["app_b"].eq(name)&links["app_a"].eq(partner))]
                st.button("查看该合作主体的技术布局",on_click=open_partner,args=(partner,))
                shared=shared_patents(bundle,name,partner,merged=merged)
                weight=selected["weight"].sum()
                source_weight=selected["p1_weight"].sum() if merged else weight
                st.write(f"{name} ↔ {partner}：展示边权 {weight:,}；当前可核验共同专利 {len(shared):,} 件；P1 原始/累加边权 {source_weight:,}。")
                if source_weight!=len(shared) and merged:
                    st.info("已核实：不同原始主体对共享同一件专利，P1 合并表按原始边权相加造成重复。此图展示证据交集的去重件数，P1 文件和图谱未改动；P2 若引用合并表会返回其累加值。")
                if int(weight)!=len(shared): st.warning("边权与当前可见专利交集不一致，可能涉及样例截取或数据范围差异；不将边权冒充可展示证据数量。")
                st.caption("两主体的精确共同申请证据见下方。问答当前按一个主体查询合作伙伴，不支持双主体交集专问。")
                ask_subject=st.selectbox("分别查询一方的合作网络",[name,partner],key="org_coop_subject")
                question_link("cooperation",ask_subject,"org_coop_ask",source_page=SUBJECTS,label="问答：所选一方的全部合作伙伴",
                        context=f"来自合作证据「{name}」↔「{partner}」：{scope_label}；交集去重 {len(shared)} 件；P1 原始/累加权重 {source_weight}。问答查询「{ask_subject}」的全部伙伴，不是两主体交集；问答若使用 P1 合并表，须区分累加值和证据去重数。")
                patent_browser(bundle,shared,key="org_shared")
except (OSError,ValueError,KeyError) as exc:data_problem(exc)
