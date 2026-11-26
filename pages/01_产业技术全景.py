"""P3: discovery, technical distributions and paginated patent evidence."""
import streamlit as st
import plotly.express as px
from analysis.page_data import dataset,overview_data,distribution,topic_history,topic_subjects,topic_patents
from ui.theme import apply_theme
from ui.components import page_header,metric_row,chart,data_problem
from ui.evidence import patent_browser,question_link,scope_notice
from ui.questions import OPERATIONS,TOPIC_ACTIONS
from ui.navigation import restore_source,OVERVIEW,subject_link
from ui.exports import summary_download
from analysis.membership import member_of
apply_theme("产业技术全景")
page_header("01 产业技术全景","在一致筛选范围内，从技术分布追溯到专利证据。")
scope_notice()
restore_source(OVERVIEW)
def reset(bounds):
    for key in list(st.session_state):
        if key.startswith("ov_"): del st.session_state[key]
    # Explicit values also clear the browser's existing widget state on the next run.
    st.session_state.update(ov_years=bounds,ov_countries=[],ov_domains=[],ov_topic_query="",ov_topic=None,
                            ov_dimension="专利类型",ov_qa_action="trend",ov_patents_query="",ov_patents_page=1,ov_patents_size=20)
try:
    bundle=dataset(); initial={"patents":bundle["tables"]["patents"],"topics":bundle["tables"]["patent_topic"]}
    with st.container(border=True):
        st.subheader("产业概况")
        a,b,c,d=st.columns([2,2,2,1])
        years=sorted(initial["patents"]["apply_year"].dropna().astype(int).unique())
        selected=a.slider("申请年份",min(years),max(years),(min(years),max(years)),key="ov_years") if len(years)>1 else None
        countries=b.multiselect("公开国别",sorted(initial["patents"]["country"].dropna().unique()),key="ov_countries")
        domains=c.multiselect("技术领域",sorted(initial["topics"]["domain"].dropna().unique()),key="ov_domains")
        d.button("重置筛选",on_click=reset,args=((min(years),max(years)),),key="ov_reset")
        year_filter=None if not selected or selected==(min(years),max(years)) else selected
        data=overview_data(year_filter,countries,domains,bundle)
        st.caption(f"当前范围：{year_filter or '全部年份（含缺失年份）'} · {', '.join(countries) or '全部公开国别'} · {', '.join(domains) or '全部领域'}；公开国别不是申请人国别。")
        metric_row([("全部专利",data["patent_count"]),("技术类专利",len(data["technical"])),("创新主体（未合并）",data["applicant_count"])])
        if bundle["subjects"].get("available"):
            trace=bundle["subjects"]["trace"]
            count=trace.loc[member_of(trace["applicant_std"],data["tables"]["applicants"]["applicant_std"]),"canonical"].nunique()
            st.caption(f"相同筛选下，已确认别名合并后有 {count:,} 个展示主体；上方卡片保留原始主体口径，与 P2 全局榜单一致。")
    with st.container(border=True):
        st.subheader("技术发展与分布")
        trend,dist,topics=st.tabs(["年度趋势","专利与技术分布","技术主题下钻"])
        with trend:
            st.caption("按申请年（非公开年）统计当前筛选全部专利，趋势只绘 2010—2023；2024—2025 不完整。")
            if data["annual"].empty: st.info("缺少完整年份数据。")
            else: chart(px.line(data["annual"],x="apply_year",y="count",markers=True))
        with dist:
            dimension=st.radio("分布维度",["专利类型","公开国别","IPC","技术功效"],horizontal=True,key="ov_dimension")
            counts=distribution(data,dimension)
            st.caption("IPC/功效以非外观设计技术类为分母；其他以全部专利为分母。同件专利可归多类。展示前 15 类。")
            if counts.empty: st.info("暂无对应分布。")
            else: chart(px.bar(counts,x=counts.columns[0],y="count"))
        with topics:
            search=st.text_input("检索技术主题",key="ov_topic_query")
            topic_names=sorted(n for n in data["topics"]["topic"].dropna().unique() if search.casefold() in n.casefold())
            if st.session_state.get("ov_topic") not in topic_names:st.session_state["ov_topic"]=None
            topic=st.selectbox("选择技术主题",[None,*topic_names],format_func=lambda x:x or "全部主题",placeholder="全部主题",key="ov_topic")
            rows=data["topics"].loc[data["topics"]["topic"].isin(topic_names)]
            ranking=rows.groupby("topic")["patent_id"].nunique().sort_values(ascending=False).head(20).reset_index(name="count")
            st.caption("当前筛选及主题检索命中范围内前 20 个规则抽取主题；“未细分”保留名称，不当作标准细粒度分类。")
            if not topic_names:st.info("当前筛选下没有匹配的技术主题，请修改检索或重置筛选。")
            if not ranking.empty: chart(px.bar(ranking,x="count",y="topic",orientation="h"))
            if topic:
                history,note=topic_history(bundle,data,topic,year_filter,countries,domains)
                st.caption(note)
                if history.empty: st.info("当前筛选下没有该主题的完整年度记录。")
                else:
                    chart(px.line(history,x="year",y="count",markers=True,labels={"year":"申请年份","count":"技术类专利数"}))
                    exported=history.assign(topic=topic)
                    summary_download(exported,"导出当前主题年度统计",key="topic_history",context=f"主题={topic}；申请年={year_filter or '2010—2023完整窗口'}；公开国别={countries or '全部'}；领域={domains or '全部'}；{note}")
                operation=st.selectbox("继续问答的内容",TOPIC_ACTIONS,format_func=lambda k:OPERATIONS[k][1],key="ov_qa_action")
                question_link(operation,topic,"ov_topic_ask",source_page=OVERVIEW,
                              context=f"来自全景页主题「{topic}」。问答只提交当前输入问题，本页年份/公开国别/领域筛选不会隐式传给后端；可在问题中明确支持的申请年范围。")
                with st.expander("查看该主题的创新主体"):
                    merged=bundle["subjects"].get("available",False)
                    owners=topic_subjects(bundle,data,topic,merged=merged).head(20)
                    st.caption("当前主题及页面筛选内的前 20 位主体，按去重专利数排序；"+("已确认别名合并。" if merged else "原始标准化主体。")+"进入主体页后查看其当前研究数据的全部技术布局，不沿用主题/国别筛选。")
                    st.dataframe(owners.rename(columns={"applicant_std":"创新主体","patent_count":"当前范围专利数"}),hide_index=True,width="stretch")
                    if not owners.empty:
                        owner=st.selectbox("继续分析创新主体",owners["applicant_std"].tolist(),key="ov_topic_subject")
                        subject_link(owner,merged=merged)
    with st.container(border=True):
        st.subheader("专利证据与详情")
        st.caption("沿用上面的申请年、公开国别、领域及所选技术主题；选中主题时，仅展示所选领域内该主题关联的技术类专利，含 2024—2025 的记录仍可查看但不进入完整年度趋势。")
        patent_browser(bundle,topic_patents(data,topic),key="ov_patents")
except (OSError,ValueError,KeyError) as exc:data_problem(exc)
