"""P3 display-only adaptation. No queries, risk judgments or business calculations."""
from html import escape
from math import isfinite
from numbers import Real

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

INTENTS = {
    "Q_TOP_APPLICANTS": ("创新主体申请量排名", "排名与主体", "bar"),
    "Q_INFLUENTIAL_APPLICANTS": ("创新主体影响力", "排名与主体", "bar"),
    "Q_COMPANY_IPC": ("主体技术领域分布", "排名与主体", "bar"),
    "Q_COOPERATION": ("共同申请与合作关系", "关系与路径", "bar"),
    "Q_TOPIC_TREND": ("技术主题年度趋势", "趋势与主题", "line"),
    "Q_GROWTH_TOPICS": ("技术主题增长", "趋势与主题", "growth"),
    "Q_COMPANY_TOPICS_DOMAIN": ("主体—主题—领域路径", "关系与路径", "path"),
    "Q_COOP_LAYOUT": ("合作主体技术布局", "关系与路径", "path"),
    "Q_CITATION_APPLICANTS": ("技术引用路径", "关系与路径", "path"),
    "Q_DEPENDENCY_EXPOSURE": ("技术依赖暴露度", "关系与路径", "exposure"),
    "Q_COMPANY_PATENTS": ("代表性专利", "排名与主体", "table"),
    "Q_TOPIC_APPLICANTS": ("技术主题创新主体排名", "趋势与主题", "bar"),
}
LABELS = ["applicant_std", "applicant", "target_applicant", "partner", "app_b", "name", "主体", "申请人", "企业", "合作主体", "topic", "主题", "ipc_code", "code", "IPC", "领域"]
METRICS = {
    "Q_TOP_APPLICANTS": ["patent_count", "application_count", "专利申请量", "专利数", "申请量", "count"],
    "Q_INFLUENTIAL_APPLICANTS": ["cited_count", "pagerank", "degree", "betweenness", "被引次数", "PageRank", "度中心性", "中介中心性"],
    "Q_COMPANY_IPC": ["patent_count", "count", "专利数", "申请量", "share", "占比"],
    "Q_COOPERATION": ["weight", "cooperation_count", "patent_count", "共同申请次数", "专利数", "count"],
    "Q_TOPIC_TREND": ["count", "patent_count", "申请量", "专利数"],
    "Q_GROWTH_TOPICS": ["growth_rate", "growth", "增长率", "增速"],
    "Q_COMPANY_TOPICS_DOMAIN": ["patent_count", "count", "专利数"],
    "Q_COOP_LAYOUT": ["patent_count", "count", "专利数"],
    "Q_CITATION_APPLICANTS": ["citation_count", "cited_count", "引证次数", "被引次数", "count"],
    "Q_DEPENDENCY_EXPOSURE": ["dependency_exposure", "exposure", "Exposure", "暴露度"],
    "Q_COMPANY_PATENTS": [],
    "Q_TOPIC_APPLICANTS": ["patent_count", "count", "专利数", "申请量"],
}
FRIENDLY = {"patent_count": "专利数", "application_count": "申请量", "cited_count": "被引次数", "pagerank": "PageRank",
            "degree": "度中心性", "betweenness": "中介中心性", "dependency_exposure": "暴露度", "exposure": "暴露度",
            "growth_rate": "增长率（后端原值）", "weight": "共同申请次数", "count": "计数"}
SCHEMA = {"APPLIES_FOR": ("Applicant", "Patent"), "CITES": ("Patent", "Patent"), "HAS_IPC": ("Patent", "IPC"),
          "INVOLVES": ("Patent", "Technology"), "BELONGS_TO": ("Technology", "Domain"), "CO_APPLIED_WITH": ("Applicant", "Applicant")}
NODE_COLORS = {"Applicant": "#00d9ef", "Patent": "#329bf5", "Technology": "#63d4b2", "Domain": "#ae9aff", "IPC": "#f3bd6a"}


def numeric_metrics(answer: dict) -> list[str]:
    return [name for name in METRICS.get(answer["intent"], [])
            if any(isinstance(row.get(name), Real) and not isinstance(row.get(name), bool)
                   and isfinite(row[name]) for row in answer["data"])]


def build_statistic(answer: dict, metric: str | None = None) -> tuple[go.Figure | None, str]:
    rows = answer["data"]
    candidates = numeric_metrics(answer)
    if not rows or not candidates:
        return None, "返回数据未提供此意图所需的数值字段，可查看数据表或关联路径。"
    metric = metric if metric in candidates else candidates[0]
    frame = pd.DataFrame(rows)
    frame = frame.loc[frame[metric].map(lambda value: isinstance(value, Real) and not isinstance(value, bool) and isfinite(value))].copy()
    frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    frame = frame.loc[frame[metric].map(lambda value: pd.notna(value) and isfinite(value))]
    label = next((name for name in LABELS if name in frame.columns), None)
    intent = answer["intent"]
    if intent == "Q_TOPIC_TREND":
        year = next((name for name in ["year", "apply_year", "年份"] if name in frame), None)
        if not year:
            return None, "未返回年度字段，不能从记录顺序推断时间趋势。"
        frame[year] = pd.to_numeric(frame[year], errors="coerce")
        frame = frame.dropna(subset=[year]).sort_values(year)
        frame = frame.loc[frame[year].between(2010, 2023)]
        group = next((name for name in ["topic", "主题"] if name in frame), None)
        if frame.empty or frame.duplicated(([group] if group else []) + [year]).any():
            return None, "年度缺失或同一序列存在重复年份，请核对后端年度统计口径。"
        fig = px.line(frame, x=year, y=metric, color=group, markers=True)
        fig.update_xaxes(dtick=1)
        fig.update_yaxes(rangemode="tozero")
        return fig, "按 P1 口径仅绘制 2010—2023；2024—2025 不完整。其余年份保留在原始返回表，不补齐缺失年份。"
    if intent == "Q_GROWTH_TOPICS":
        count = next((name for name in ["patent_count", "count", "申请量", "专利数"] if name in frame and pd.to_numeric(frame[name], errors="coerce").notna().any()), None)
        if count:
            frame[count] = pd.to_numeric(frame[count], errors="coerce")
            frame = frame.dropna(subset=[count])
            fig = px.scatter(frame, x=count, y=metric, hover_name=label)
            if not frame.empty:
                fig.add_vline(x=float(frame[count].median()), line_dash="dot", line_color="#54758c")
                fig.add_hline(y=float(frame[metric].median()), line_dash="dot", line_color="#54758c")
            return fig, "四象限参考线为当前返回记录的中位数，仅辅助阅读；增长率保留后端原单位，不作为行业阈值。"
    if not label:
        return None, "未返回主体、主题或分类标签，页面不推断指标所属实体。"
    if intent == "Q_DEPENDENCY_EXPOSURE" and not frame[metric].between(0, 1).all():
        return None, "暴露度不在约定的 0—1 范围内，请核对后端单位；页面没有截断或换算异常值。"
    frame = frame.dropna(subset=[label]).sort_values(metric)
    fig = px.bar(frame, x=metric, y=label, orientation="h", text_auto=".3g")
    fig.update_xaxes(title=FRIENDLY.get(metric, metric), rangemode="tozero")
    fig.update_yaxes(title=None)
    if intent == "Q_DEPENDENCY_EXPOSURE":
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
    return fig, "仅展示本次返回记录；未合并未返回的主体、主题或指标。"


def metric_cards(answer: dict) -> list[tuple[str, str]]:
    cards = []
    for field in numeric_metrics(answer)[:3]:
        values = [float(row[field]) for row in answer["data"] if isinstance(row.get(field), Real)
                  and not isinstance(row.get(field), bool) and isfinite(row[field])]
        value = max(values)
        if answer["intent"] == "Q_DEPENDENCY_EXPOSURE":
            if not 0 <= value <= 1:
                continue
            text = f"{value:.1%}"
        else:
            text = f"{value:,.0f}" if value.is_integer() else f"{value:,.3f}"
        cards.append(("当前返回最高 · " + FRIENDLY.get(field, field), text))
    if answer["intent"] == "Q_DEPENDENCY_EXPOSURE":
        for names, label in [(["C_A", "citing_total", "total_citations", "引证总数"], "返回引证总数 C_A"),
                             (["c_AB", "citation_count", "引证次数"], "当前返回最高 · 引证次数")]:
            field = next((name for name in names if any(isinstance(row.get(name), Real) and not isinstance(row[name], bool) and isfinite(row[name]) for row in answer["data"])), None)
            values = [float(row[field]) for row in answer["data"] if field and isinstance(row.get(field), Real) and not isinstance(row[field], bool) and isfinite(row[field])]
            if values and (label != "返回引证总数 C_A" or len(set(values)) == 1):
                value = max(values)
                cards.append((label, f"{value:,.0f}" if value.is_integer() else f"{value:,.3f}"))
    return cards


def validated_graph(graph: dict) -> tuple[list, list, list[str]]:
    nodes, edges, notes, ids = [], [], [], set()
    for node in graph["nodes"]:
        if not isinstance(node, dict) or not all(isinstance(node.get(k), str) and node[k] for k in ["id", "label", "type"]) or node["id"] in ids:
            notes.append("存在无效或重复节点，已从绘图中排除；原始返回仍可在溯源查看。")
            continue
        nodes.append(node)
        ids.add(node["id"])
    types = {n["id"]: n["type"] for n in nodes}
    for edge in graph["edges"]:
        if (not isinstance(edge, dict) or not isinstance(edge.get("source"), str)
                or not isinstance(edge.get("target"), str) or edge["source"] not in ids or edge["target"] not in ids):
            notes.append("存在缺少端点的关系，页面未创建占位节点。")
            continue
        pair = (types[edge["source"]], types[edge["target"]])
        if not isinstance(edge.get("type"), str) or edge["type"] not in SCHEMA or SCHEMA[edge["type"]] != pair:
            notes.append("存在与冻结 Schema 不符的关系，已排除绘图，请核对后端。")
            continue
        edges.append(edge)
    return nodes, edges, list(dict.fromkeys(notes))


def graph_figure(graph: dict, *, height: int = 370) -> tuple[go.Figure | None, list[str]]:
    nodes, edges, notes = validated_graph(graph)
    if not nodes:
        return None, notes
    network = nx.Graph()
    network.add_nodes_from(n["id"] for n in nodes)
    network.add_edges_from((edge["source"], edge["target"]) for edge in edges)
    positions = nx.spring_layout(network, seed=42, k=1.5)
    figure = go.Figure()
    edge_x, edge_y, label_x, label_y, labels, edge_meta = [], [], [], [], [], []
    for index, edge in enumerate(edges):
        a, b = positions[edge["source"]], positions[edge["target"]]
        edge_x.extend([a[0], b[0], None]); edge_y.extend([a[1], b[1], None])
        label_x.append((a[0] + b[0]) / 2); label_y.append((a[1] + b[1]) / 2)
        labels.append(escape(edge["type"]))
        edge_meta.append(["edge", str(index), escape(edge["source"]), escape(edge["target"]), escape(edge["type"])])
        if edge["type"] != "CO_APPLIED_WITH":
            figure.add_annotation(x=a[0] + .83 * (b[0] - a[0]), y=a[1] + .83 * (b[1] - a[1]),
                                  ax=a[0] + .68 * (b[0] - a[0]), ay=a[1] + .68 * (b[1] - a[1]),
                                  xref="x", yref="y", axref="x", ayref="y", text="", showarrow=True,
                                  arrowhead=3, arrowsize=1.2, arrowwidth=1.5, arrowcolor="#00d9ef")
    figure.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line={"color": "#27778e", "width": 1.6},
                               hoverinfo="skip", showlegend=False))
    figure.add_trace(go.Scatter(x=label_x, y=label_y, mode="markers+text", text=labels,
                               textposition="top center", textfont={"size": 9, "color": "#9ecbd9"},
                               marker={"size": 18, "opacity": .08, "color": "#00d9ef"}, customdata=edge_meta,
                               hovertemplate="%{customdata[2]} → %{customdata[3]}<br>%{customdata[4]}<extra></extra>", showlegend=False))
    for kind in dict.fromkeys(n["type"] for n in nodes):
        subset = [n for n in nodes if n["type"] == kind]
        figure.add_trace(go.Scatter(
            x=[positions[n["id"]][0] for n in subset], y=[positions[n["id"]][1] for n in subset],
            mode="markers+text", name=kind, text=[escape(n["label"]) for n in subset], textposition="bottom center",
            textfont={"size": 11}, marker={"size": 24, "color": NODE_COLORS.get(kind, "#8ca4b5"), "line": {"width": 2, "color": "#a9edf3"}},
            customdata=[["node", n["id"], escape(n["label"]), escape(n["type"])] for n in subset],
            hovertemplate="%{customdata[2]}<br>类型：%{customdata[3]}<br>ID：%{customdata[1]}<extra></extra>"))
    figure.update_layout(height=height, dragmode="pan", clickmode="event+select", uirevision="ev-graph",
                         margin={"l": 30, "r": 30, "t": 35, "b": 50},
                         xaxis={"visible": False, "range": [-1.4, 1.4]}, yaxis={"visible": False, "range": [-1.45, 1.35]},
                         legend={"orientation": "h", "y": 1.1, "x": 0, "font": {"size": 10}})
    return figure, notes
