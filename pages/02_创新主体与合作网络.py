"""P3: consume P1's metrics. Heavy algorithms stay in scripts/."""
import plotly.express as px
import streamlit as st

from analysis.page_data import applicant_metrics
from ui.theme import apply_theme
from ui.components import page_header, section, chart, data_table, empty_state, error_state

apply_theme("创新主体与合作网络")
page_header("02 创新主体与合作网络", "指标由 P1 预计算；合作网络交互由 P3 后续完善。")
top_n = st.selectbox("展示数量", [10, 20, 50])
try:
    metrics = applicant_metrics(top_n)
    section("创新主体申请量排名")
    if metrics.empty:
        empty_state()
    else:
        chart(px.bar(metrics, x="applicant_std", y="patent_count", labels={"applicant_std": "创新主体", "patent_count": "专利数"}))
    section("主体指标明细")
    data_table(metrics)
    st.caption("引用网络仅包含当前研究数据内两端专利；外部引用不计入这些指标。")
except (FileNotFoundError, ValueError) as exc:
    error_state(str(exc))
