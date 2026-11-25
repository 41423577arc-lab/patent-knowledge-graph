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
