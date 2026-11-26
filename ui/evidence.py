"""P3 reusable patent evidence, pagination and explicit QA handoff."""
import pandas as pd
import streamlit as st
from analysis.page_data import patent_selection, page_slice, patent_detail, patent_citation_stats
from ui.questions import subject_question,build_question,template_entities,UnsupportedTemplate
from ui.navigation import capture_source,OVERVIEW,SUBJECTS,QA


def qa_link(question, key, *, label="带入智能问答", context=None,source_page=None):
    if st.button(label, key=key, icon=":material/chat:"):
        st.session_state["ev_qa_prefill"] = question
        st.session_state["ev_qa_context"] = context
        source_page=source_page or (SUBJECTS if key.startswith("org_") else OVERVIEW if key.startswith("ov_") else None)
        origin=capture_source(source_page)
        st.session_state["ev_qa_origin"]=origin
        st.session_state["ev_last_origin"]=origin
        st.session_state["ev_qa_template_entities"]=template_entities(question)
        st.switch_page(QA)


def question_link(operation,name,key,*,label="带入智能问答",context=None,source_page=None,years=None):
    try:
        question=build_question(operation,name,years)
    except UnsupportedTemplate as exc:
        st.info(f"此问答操作暂不可用：{exc} 当前页面证据仍可查看。")
        return
    qa_link(question,key,label=label,context=context,source_page=source_page)


def scope_notice():
    from core import config
    st.caption(("真实开发样例：不用于推断全量产业规模或市场趋势。" if config.USE_SAMPLE else "全量研究数据：不是随机全产业样本。") +
               (" 问答当前为模拟桩。" if config.QA_BACKEND == "mock" else " 问答当前为正式服务入口，执行模式以后端返回为准。"))


def locate_patent(patent_id):
    """Resolve an exact returned ID in the active P1 scope, without another QA call."""
    from analysis.page_data import dataset
    bundle=dataset()
    current=patent_selection(bundle,query="")
    if patent_id not in set(current["patent_id"]):
        st.info("该编号不在当前七表专利范围；可能属于 P1 外部引用辅助证据。请对照本次返回来源，不将其视为已入库专利详情。")
        return
    detail=patent_detail(bundle,patent_id)
    st.caption("当前固定 P1 数据中的精确编号证据（不会再次调用问答服务）")
    st.write("编号：",patent_id)
    st.write("标题：",detail["patent"].get("title") or "未提供")
    st.write("申请年：",str(detail["patent"].get("apply_year")))
    st.dataframe(detail["applicants"][["applicant_raw","applicant_std"]],hide_index=True,width="stretch")
    st.dataframe(detail["patent_ipc"].drop(columns="patent_id"),hide_index=True,width="stretch")


def patent_browser(bundle, patents=None, *, key, topic=None, domain=None):
    query=st.text_input("检索专利标题或编号",key=f"{key}_query")
    frame=patent_selection(bundle,patents,query,topic,domain)
    size=st.selectbox("每页条数",[10,20,50],index=1,key=f"{key}_size")
    _,_,pages=page_slice(frame,1,size)
    page_key=f"{key}_page"
    if st.session_state.get(page_key,1)>pages: st.session_state[page_key]=1
    number=st.number_input("页码",min_value=1,max_value=pages,value=1,step=1,key=page_key)
    shown,number,pages=page_slice(frame,number,size)
    st.caption(f"找到 {len(frame):,} 件；第 {number}/{pages} 页。仅渲染当前页。")
    if shown.empty:
        st.info("当前条件下没有专利证据。")
        return
    columns=[c for c in ["patent_id","title","apply_date","patent_type","country"] if c in shown]
    st.dataframe(shown[columns],hide_index=True,width="stretch")
    st.caption("专利明细仅供分页查看；批量明细下载的授权范围尚未确认，当前只开放统计汇总导出。")
    labels=dict(zip(shown["patent_id"],shown["title"].fillna("未提供标题")))
    patent_id=st.selectbox("选择专利查看详情",shown["patent_id"].tolist(),format_func=lambda p:f"{p} · {labels[p]}",key=f"{key}_detail")
    detail=patent_detail(bundle,patent_id)
    with st.expander("专利详细信息",expanded=True):
        citations=patent_citation_stats(bundle,patent_id)
        a,b,c=st.columns(3)
        a.metric("研究范围内被引次数",citations["cited_count"])
        b.metric("已收录引用专利数",citations["citing_count"])
        c.metric("其中研究范围外",citations["external_citing_count"])
        st.caption("按当前引用表的有向专利对去重；引用总数含范围内外。零表示当前表未收录对应边，不代表从未引用或被引，也非全产业被引次数。")
        for name,label in [("title","标题"),("patent_id","编号"),("abstract","摘要"),("apply_date","申请日期"),("pub_date","公开日期"),("patent_type","专利类型"),("legal_status","法律状态")]:
            value=detail["patent"].get(name)
            st.write(f"{label}：", "未提供" if value is None or pd.isna(value) or value=="" else str(value))
        for table,label in [("applicants","申请主体"),("patent_ipc","IPC"),("patent_topic","技术主题与领域")]:
            st.caption(label)
            if detail[table].empty: st.write("未提供")
            else: st.dataframe(detail[table].drop(columns="patent_id"),hide_index=True,width="stretch")
        names=detail["applicants"]["applicant_std"].dropna().unique().tolist()
        st.caption("单篇专利的真实详情已展示在上方。问答目前支持申请人级查询，以下入口查询该申请人的代表性专利，不保证包含当前专利。")
        if names:
            subject=st.selectbox("选择要继续查询的申请主体",names,key=f"{key}_qa_subject")
            question_link("patents",subject,f"{key}_ask",label="问答：该申请人的代表性专利",
                    context=f"来自专利 {patent_id}；本次问答查询申请主体「{subject}」的代表性专利，并非按该专利编号检索。")
        else: st.info("未提供申请主体，暂不能生成申请人级问答。")
