"""P3 reusable patent evidence, pagination and explicit QA handoff."""
import pandas as pd
import streamlit as st
from analysis.page_data import patent_selection, page_slice, patent_detail


def qa_link(question, key):
    if st.button("带入智能问答", key=key, icon=":material/chat:"):
        st.session_state["ev_qa_prefill"] = question
        st.switch_page("pages/03_智能问答与关联路径.py")


def scope_notice():
    from core import config
    st.caption(("真实开发样例：不用于推断全量产业规模或市场趋势。" if config.USE_SAMPLE else "全量研究数据：不是随机全产业样本。") +
               (" 问答当前为模拟桩。" if config.QA_BACKEND == "mock" else " 问答当前为正式服务入口，执行模式以后端返回为准。"))


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
    labels=dict(zip(shown["patent_id"],shown["title"].fillna("未提供标题")))
    patent_id=st.selectbox("选择专利查看详情",shown["patent_id"].tolist(),format_func=lambda p:f"{p} · {labels[p]}",key=f"{key}_detail")
    detail=patent_detail(bundle,patent_id)
    with st.expander("专利详细信息",expanded=True):
        for name,label in [("title","标题"),("patent_id","编号"),("abstract","摘要"),("apply_date","申请日期"),("pub_date","公开日期"),("patent_type","专利类型"),("legal_status","法律状态")]:
            value=detail["patent"].get(name)
            st.write(f"{label}：", "未提供" if value is None or pd.isna(value) or value=="" else str(value))
        for table,label in [("applicants","申请主体"),("patent_ipc","IPC"),("patent_topic","技术主题与领域")]:
            st.caption(label)
            if detail[table].empty: st.write("未提供")
            else: st.dataframe(detail[table].drop(columns="patent_id"),hide_index=True,width="stretch")
        qa_link(f"请介绍专利 {patent_id} 的技术内容与关联主体。",f"{key}_ask")
