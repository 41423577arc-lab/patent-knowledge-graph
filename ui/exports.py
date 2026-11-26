"""Only explicitly selected aggregate columns may be downloaded by P3 pages."""
import streamlit as st

SUMMARY_COLUMNS={"applicant_std","canonical","raw_members","patent_count","cited_count","pagerank","degree","betweenness",
                 "year","apply_year","count","ipc_code","topic","domain","专利数","country","patent_type","efficacy_l1",
                 "app_a","app_b","weight","p1_weight","shared_count"}


def summary_csv(frame,context):
    if set(frame.columns)-SUMMARY_COLUMNS:raise ValueError("该导出包含未经允许的明细字段")
    output=frame.copy()
    output["统计范围"]=context
    return output.to_csv(index=False).encode("utf-8-sig")


def summary_download(frame,label,*,key,context):
    if frame.empty:return
    st.download_button(label,summary_csv(frame,context),file_name=f"{key}.csv",mime="text/csv",key=key,on_click="ignore")
