"""P1: application shell. Business pages belong to P2/P3."""
import streamlit as st

from core import config
from core.data_loader import available_tables

st.set_page_config(page_title="EV Intelligence", page_icon="🔋", layout="wide")
st.title("新能源汽车产业技术情报平台")
st.caption("团队开发基线 · 三页功能由 P2 / P3 分别开发")
st.info("当前为样例模式" if config.USE_SAMPLE else "当前为全量模式")
st.write("可用数据表：", ", ".join(available_tables()) or "尚未生成，请参照 docs/run.md")
st.page_link("pages/01_产业技术全景.py", label="产业技术全景")
st.page_link("pages/02_创新主体与合作网络.py", label="创新主体与合作网络")
st.page_link("pages/03_智能问答与关联路径.py", label="智能问答与关联路径")
