"""P3: homepage, navigation and global presentation."""
import streamlit as st

from core import config
from core.data_loader import available_tables
from ui.theme import apply_theme
from ui.components import page_header

apply_theme()
page_header("新能源汽车产业技术情报平台", "P1 数据与指标 · P2 智能问答 · P3 统一前端")
if config.QA_BACKEND == "mock":
    st.warning("当前为问答演示桩模式：仅支持三个明确标注为假数据的示例。设置 QA_BACKEND=real 并连接匹配范围的 Neo4j 后，可启用已实现的 12 类真实问答。")
else:
    st.info("真实问答后端已实现 12 类意图，支持规则问答及可选 LLM 增强；实际查询需要连接与 USE_SAMPLE 数据范围一致的 Neo4j。")
st.write("可用数据表：", ", ".join(available_tables()) or "尚未生成，请参照 docs/run.md")
st.page_link("pages/01_产业技术全景.py", label="产业技术全景")
st.page_link("pages/02_创新主体与合作网络.py", label="创新主体与合作网络")
st.page_link("pages/03_智能问答与关联路径.py", label="智能问答与关联路径")
