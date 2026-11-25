"""P3: panorama page; all page data comes through analysis/page_data.py."""
import plotly.express as px

from analysis.page_data import overview_data, topic_year
from ui.theme import apply_theme
from ui.components import page_header, metric_row, section, chart, data_table, empty_state, error_state

apply_theme("产业技术全景")
page_header("01 产业技术全景", "统计样本内专利；缺失日期不会被补成虚构年份。")
try:
    data = overview_data()
    metric_row([("专利数", data["patent_count"]), ("创新主体数", data["applicant_count"]), ("主 IPC 数", data["ipc_count"])])
    section("申请年度趋势")
    if data["annual"].empty:
        empty_state("当前数据缺少可靠申请年，暂不绘制年度趋势。")
    else:
        chart(px.line(data["annual"], x="apply_year", y="count", markers=True))
    section("技术主题年度表")
    data_table(topic_year())
    section("专利明细（前 20 条）")
    data_table(data["patents"].head(20))
except (FileNotFoundError, ValueError) as exc:
    error_state(str(exc))
