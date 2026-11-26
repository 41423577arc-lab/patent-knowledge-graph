"""P3: common headers, numbers, plots, tables and empty/error states."""
from numbers import Integral, Real

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

from core import config
from ui.assets import heading_html
from ui.theme import PLOTLY_TEMPLATE


def page_header(title: str, subtitle: str = "") -> None:
    number = title[:2] if title[:2].isdigit() else "EV"
    name = title[3:] if title[:2].isdigit() else title
    st.html(heading_html(name, subtitle, number))
    st.caption("数据范围：开发样例" if config.USE_SAMPLE else "数据范围：全量研究样本")


def section(title: str) -> None:
    st.subheader(title)


def format_number(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Integral):
        return f"{value:,}"
    if isinstance(value, Real):
        return f"{value:,.3f}"
    return str(value)


def metric_row(items: list[tuple[str, object]]) -> None:
    for column, (label, value) in zip(st.columns(len(items)), items):
        column.metric(label, format_number(value))


def chart(figure) -> None:
    figure.update_layout(template=PLOTLY_TEMPLATE)
    st.plotly_chart(figure, width="stretch", theme=None)


def data_table(table) -> None:
    if len(table) == 0:
        empty_state()
    else:
        st.dataframe(table, hide_index=True, width="stretch")


def empty_state(message: str = "当前筛选条件下暂无数据。") -> None:
    st.info(message)


def error_state(message: str) -> None:
    st.error(message)


def data_problem(exc):
    if isinstance(exc,FileNotFoundError):message="当前研究数据文件缺失，请检查 DATA_DIR 与固定数据目录。"
    elif isinstance(exc,PermissionError):message="当前研究数据文件无法读取，请检查文件访问权限。"
    elif isinstance(exc,OSError):message="当前研究数据文件读取失败，请检查磁盘或文件是否可用。"
    else:message="当前数据结构或版本校验未通过，请核对固定来源、字段与指标清单。"
    st.error(message)
    st.caption("当前查询未完成。侧栏导航仍可使用；修复数据后可重新读取。")
    from analysis.page_data import _clear_snapshot
    st.button("重新读取当前数据",on_click=_clear_snapshot,key="ev_retry_data")


def path_graph(graph: dict) -> None:
    """NetworkX is used for layout only; metrics are precomputed by P1."""
    if not graph["nodes"]:
        empty_state("本次回答没有关联路径。")
        return
    network = nx.DiGraph()
    for node in graph["nodes"]:
        network.add_node(node["id"], label=node["label"])
    for edge in graph["edges"]:
        network.add_edge(edge["source"], edge["target"])
    positions = nx.spring_layout(network, seed=42)
    x, y = [], []
    for source, target in network.edges():
        x.extend([positions[source][0], positions[target][0], None])
        y.extend([positions[source][1], positions[target][1], None])
    figure = go.Figure(go.Scatter(x=x, y=y, mode="lines", hoverinfo="skip", showlegend=False))
    figure.add_trace(go.Scatter(
        x=[positions[n][0] for n in network], y=[positions[n][1] for n in network],
        text=[network.nodes[n]["label"] for n in network], mode="markers+text",
        textposition="top center", marker={"size": 16}, showlegend=False,
    ))
    figure.update_layout(xaxis={"visible": False}, yaxis={"visible": False}, height=350)
    chart(figure)
    st.caption("连线仅展示布局，方向与关系类型以路径明细为准。")
    data_table(graph["edges"])
