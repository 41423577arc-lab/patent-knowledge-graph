# -*- coding: utf-8 -*-
"""验证 6 个能力问题对应的 Cypher 查询，并把结果写入 docs/verify.txt。"""
import os, time
from pathlib import Path
import pandas as pd
from neo4j import GraphDatabase

URI = os.environ.get("KG_NEO4J_URI", "bolt://127.0.0.1:7687")
drv = GraphDatabase.driver(URI, auth=("neo4j", "kgpatent2026"))
out = []

QUERIES = {
"Q1 企业专利数与授权率": """
    MATCH (c:Company {name:$name})-[:APPLIED]->(p:Patent)
    RETURN count(p) AS 专利数, sum(p.is_granted) AS 授权数, sum(p.is_rejected) AS 驳回数
""",
"Q2 企业技术布局": """
    MATCH (c:Company {name:$name})-[:APPLIED]->(p:Patent)-[:IN_CLASS]->(t:TechClass)
    RETURN t.sector AS 技术板块, count(*) AS 专利数 ORDER BY 专利数 DESC
""",
"Q3 谁引用该企业专利（2跳）": """
    MATCH (a:Company {name:$name})-[:APPLIED]->(:Patent)-[:CITES]->(p2:Patent)<-[:APPLIED]-(b:Company)
    WHERE b.name <> $name
    RETURN b.name AS 引用方, count(DISTINCT p2) AS 引用专利数 ORDER BY 引用专利数 DESC LIMIT 10
""",
"Q5 核心专利": """
    MATCH (p:Patent)<-[r:CITES]-()
    WHERE p.title IS NOT NULL
    RETURN p.id AS 公开号, p.title AS 标题, p.year AS 年份, count(r) AS 被引次数
    ORDER BY 被引次数 DESC LIMIT 10
""",
"Q6 技术板块年度趋势": """
    MATCH (p:Patent)-[:IN_CLASS]->(t:TechClass)
    WHERE p.year >= 2015 AND p.year <= 2025
    RETURN p.year AS 年份, t.sector AS 板块, count(*) AS 数量
    ORDER BY 年份 LIMIT 12
""",
}

def run(cypher, **kw):
    t = time.time()
    with drv.session() as s:
        rows = [r.data() for r in s.run(cypher, **kw)]
    return pd.DataFrame(rows), time.time() - t

with drv.session() as s:
    top = [r["name"] for r in s.run("""
        MATCH (c:Company)-[:APPLIED]->(:Patent) WITH c, count(*) AS n
        ORDER BY n DESC LIMIT 5 RETURN c.name AS name""")]
out.append("Top companies: %r" % top)

name = top[0]
for label, cypher in QUERIES.items():
    df, dt = run(cypher, name=name)
    out.append("\n=== %s (%.2fs) ===" % (label, dt))
    out.append(df.head(10).to_string(index=False))

Path("kg_system/docs/verify.txt").write_text("\n".join(out), encoding="utf-8")
drv.close()
print("written")
