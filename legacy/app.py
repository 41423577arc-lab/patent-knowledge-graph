# -*- coding: utf-8 -*-
"""新能源汽车专利知识图谱 · 演示系统（Streamlit + Neo4j）"""
import os
import pandas as pd
import streamlit as st
import plotly.express as px
from neo4j import GraphDatabase

from core.config import NEO4J_URI as URI, NEO4J_USER as USER, NEO4J_PASSWORD as PWD

st.set_page_config(page_title="新能源汽车专利知识图谱", page_icon="🔋", layout="wide")


@st.cache_resource
def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PWD))


@st.cache_data(ttl=300)
def q(cypher, **params):
    with get_driver().session() as s:
        return pd.DataFrame([r.data() for r in s.run(cypher, **params)])


def head_counts():
    nodes = q("MATCH (n) RETURN labels(n)[0] AS 类型, count(*) AS 数量 ORDER BY 数量 DESC")
    rels = q("MATCH ()-[r]->() RETURN type(r) AS 关系, count(*) AS 数量 ORDER BY 数量 DESC")
    return nodes, rels


st.sidebar.title("🔋 专利知识图谱")
st.sidebar.caption("新能源汽车技术布局 · Neo4j")
page = st.sidebar.radio("功能", ["图谱概览", "企业技术画像", "引用关系多跳分析", "核心专利识别", "技术演进趋势", "专利检索"])

if page == "图谱概览":
    st.title("图谱概览")
    nodes, rels = head_counts()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("实体规模")
        st.dataframe(nodes, width="stretch", hide_index=True)
    with c2:
        st.subheader("关系规模")
        st.dataframe(rels, width="stretch", hide_index=True)

    sector = q("""
        MATCH (p:Patent)-[:IN_CLASS]->(t:TechClass)
        RETURN t.sector AS 技术板块, count(*) AS 专利数
        ORDER BY 专利数 DESC
    """)
    st.subheader("技术板块分布")
    st.plotly_chart(px.bar(sector, x="技术板块", y="专利数", color="技术板块"), width="stretch")

    top = q("""
        MATCH (c:Company)-[:APPLIED]->(p:Patent)
        RETURN c.name AS 企业, count(p) AS 专利数
        ORDER BY 专利数 DESC LIMIT 15
    """)
    st.subheader("专利数量 Top 15 企业")
    st.plotly_chart(px.bar(top, x="专利数", y="企业", orientation="h"), width="stretch")

elif page == "企业技术画像":
    st.title("企业技术画像")
    companies = q("""
        MATCH (c:Company)-[:APPLIED]->(:Patent)
        WITH c, count(*) AS n WHERE n >= 10
        RETURN c.name AS name ORDER BY n DESC LIMIT 300
    """)["name"].tolist()
    name = st.selectbox("选择企业", companies)
    if name:
        base = q("""
            MATCH (c:Company {name:$name})-[:APPLIED]->(p:Patent)
            RETURN count(p) AS 专利数,
                   sum(p.is_granted) AS 授权数,
                   sum(p.is_rejected) AS 驳回数,
                   avg(p.n_cited) AS 平均被引
        """, name=name).iloc[0]
        a, b, c, d = st.columns(4)
        a.metric("专利总数", int(base["专利数"]))
        b.metric("授权", int(base["授权数"] or 0))
        c.metric("驳回", int(base["驳回数"] or 0))
        rate = (base["授权数"] or 0) / max(1, base["专利数"])
        d.metric("授权率", f"{rate:.1%}")

        sec = q("""
            MATCH (c:Company {name:$name})-[:APPLIED]->(p:Patent)-[:IN_CLASS]->(t:TechClass)
            RETURN t.sector AS 技术板块, count(*) AS 专利数 ORDER BY 专利数 DESC
        """, name=name)
        cls = q("""
            MATCH (c:Company {name:$name})-[:APPLIED]->(p:Patent)-[:IN_CLASS]->(t:TechClass)
            RETURN t.code AS IPC小类, t.sector AS 技术板块, count(*) AS 专利数
            ORDER BY 专利数 DESC LIMIT 10
        """, name=name)
        left, right = st.columns(2)
        with left:
            st.subheader("技术板块布局")
            st.plotly_chart(px.bar(sec, x="技术板块", y="专利数", color="技术板块"), width="stretch")
        with right:
            st.subheader("Top 10 IPC 小类")
            st.dataframe(cls, width="stretch", hide_index=True)

        top_p = q("""
            MATCH (c:Company {name:$name})-[:APPLIED]->(p:Patent)
            OPTIONAL MATCH (p)<-[r:CITES]-()
            WITH p, count(r) AS 被引次数
            RETURN p.id AS 公开号, p.title AS 标题, p.year AS 年份,
                   p.legal AS 法律状态, 被引次数
            ORDER BY 被引次数 DESC LIMIT 15
        """, name=name)
        st.subheader("代表性专利（按被引次数）")
        st.dataframe(top_p, width="stretch", hide_index=True)

elif page == "引用关系多跳分析":
    st.title("引用关系多跳分析")
    st.caption("路径：企业 A —申请→ 专利 —引用→ 专利 ←申请— 企业 B（2 跳）")
    companies = q("""
        MATCH (c:Company)-[:APPLIED]->(:Patent)
        WITH c, count(*) AS n WHERE n >= 10
        RETURN c.name AS name ORDER BY n DESC LIMIT 300
    """)["name"].tolist()
    name = st.selectbox("企业 A", companies)
    if name:
        flow = q("""
            MATCH (a:Company {name:$name})-[:APPLIED]->(p1:Patent)-[:CITES]->(p2:Patent)<-[:APPLIED]-(b:Company)
            WHERE b.name <> $name
            RETURN b.name AS 引用方企业, count(DISTINCT p2) AS 引用专利数
            ORDER BY 引用专利数 DESC LIMIT 20
        """, name=name)
        st.subheader("谁在引用这家企业的专利")
        if flow.empty:
            st.info("图中没有找到引用关系（可能该企业专利未被数据集内企业引用）")
        else:
            st.plotly_chart(px.bar(flow, x="引用专利数", y="引用方企业", orientation="h"), width="stretch")
            st.dataframe(flow, width="stretch", hide_index=True)

        paths = q("""
            MATCH (a:Company {name:$name})-[:APPLIED]->(p1:Patent)-[:CITES]->(p2:Patent)<-[:APPLIED]-(b:Company)
            WHERE b.name <> $name
            RETURN a.name AS 起点企业, p1.id AS 专利A, p1.title AS 标题A,
                   p2.id AS 专利B, p2.title AS 标题B, b.name AS 目标企业
            LIMIT 30
        """, name=name)
        st.subheader("多跳路径样例")
        st.dataframe(paths, width="stretch", hide_index=True)

elif page == "核心专利识别":
    st.title("核心专利识别")
    st.caption("以「被引用次数」衡量专利影响力（图上的入度）")
    top = q("""
        MATCH (p:Patent)<-[r:CITES]-()
        WHERE p.title IS NOT NULL
        WITH p, count(r) AS 被引次数
        RETURN p.id AS 公开号, p.title AS 标题, p.year AS 年份,
               p.legal AS 法律状态, 被引次数
        ORDER BY 被引次数 DESC LIMIT 30
    """)
    st.dataframe(top, width="stretch", hide_index=True)

    hub = q("""
        MATCH (c:Company)-[:APPLIED]->(p:Patent)<-[r:CITES]-()
        RETURN c.name AS 企业, count(r) AS 被引总次数
        ORDER BY 被引总次数 DESC LIMIT 15
    """)
    st.subheader("被引最多的企业（技术影响力）")
    st.plotly_chart(px.bar(hub, x="被引总次数", y="企业", orientation="h"), width="stretch")

elif page == "技术演进趋势":
    st.title("技术演进趋势")
    year = q("""
        MATCH (p:Patent)-[:IN_CLASS]->(t:TechClass)
        WHERE p.year >= 2010 AND p.year <= 2025
        RETURN p.year AS 年份, t.sector AS 技术板块, count(*) AS 专利数
        ORDER BY 年份
    """)
    fig = px.line(year, x="年份", y="专利数", color="技术板块", markers=True)
    st.plotly_chart(fig, width="stretch")
    st.caption("来源：4 个 incoPat 导出文件，按申请/公开年份统计（含驳回专利）")

else:
    st.title("专利检索")
    kw = st.text_input("标题关键词（如：电池、热管理、充电）", "电池")
    if kw:
        res = q("""
            MATCH (p:Patent)
            WHERE p.title CONTAINS $kw
            OPTIONAL MATCH (c:Company)-[:APPLIED]->(p)
            RETURN p.id AS 公开号, p.title AS 标题, c.name AS 申请人,
                   p.year AS 年份, p.legal AS 法律状态, p.ipc_main AS 主分类
            LIMIT 100
        """, kw=kw)
        st.write(f"命中 {len(res)} 条（最多显示 100 条）")
        st.dataframe(res, width="stretch", hide_index=True)

st.sidebar.divider()
st.sidebar.caption("数据：incoPat 专利著录项（公开数据）\n仅用于课程演示，不含个人隐私信息")
