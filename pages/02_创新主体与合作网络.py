"""P2 owns this page; implement network metrics in analysis/."""
import streamlit as st

from core.data_loader import load_table

st.title("创新主体与合作网络")
st.info("P2 开发入口：主体排名、网络中心性、企业详情与合作下钻。")
try:
    st.dataframe(load_table("applicants").head(20), hide_index=True)
except (FileNotFoundError, ValueError) as exc:
    st.warning(str(exc))
