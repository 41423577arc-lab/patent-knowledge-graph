"""P2 owns this page; implement aggregates in analysis/."""
import streamlit as st

from core.data_loader import load_table

st.title("产业技术全景")
st.info("P2 开发入口：年度趋势、IPC 分布、技术功效与主题热力。")
try:
    st.dataframe(load_table("patents").head(20), hide_index=True)
except (FileNotFoundError, ValueError) as exc:
    st.warning(str(exc))
