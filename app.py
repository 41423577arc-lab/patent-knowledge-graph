"""P3: homepage, navigation and global presentation."""
import streamlit as st

from core import config
from core.data_loader import available_tables
from ui.theme import apply_theme
from ui.components import page_header

apply_theme()
page_header("新能源汽车产业技术情报平台", "P1 数据与指标 · P2 问答服务 · P3 统一前端")
if config.QA_BACKEND == "mock":
    st.warning("问答处于演示桩模式：假数据仅供页面开发，不是实际分析结论。")
else:
    st.info("问答使用真实服务入口；当前真实问答实现仍待 P2 完成。")
st.write("可用数据表：", ", ".join(available_tables()) or "尚未生成，请参照 docs/run.md")
st.page_link("pages/01_产业技术全景.py", label="产业技术全景")
st.page_link("pages/02_创新主体与合作网络.py", label="创新主体与合作网络")
st.page_link("pages/03_智能问答与关联路径.py", label="智能问答与关联路径")
