"""Build the contract-A Neo4j graph from the seven contract-C tables.

Default: full tables in ``data/processed``.  ``--sample`` builds the development
sample instead.  The importer is intentionally explicit:

- refuses to add a second copy into a non-empty contract graph unless ``--reset``;
- creates the v2 constraints/indexes first and waits for them;
- imports only in-sample CITES edges (external citations stay in the auxiliary
  applicant table, per the project decision);
- verifies every node and relationship count against the parquet inputs;
- writes ``data/results/scale.json`` and the P1-7 delivery folder.

Run with the project venv: ``python -m scripts.build_graph``.
"""
import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

from core import config
from core.data_loader import TABLE_COLUMNS

NODES = ["Patent", "Applicant", "IPC", "Technology", "Domain"]
RELS = ["APPLIES_FOR", "CITES", "HAS_IPC", "INVOLVES", "BELONGS_TO", "CO_APPLIED_WITH"]

CONSTRAINTS = [
    "CREATE CONSTRAINT patent_id_v2 IF NOT EXISTS FOR (n:Patent) REQUIRE n.patent_id IS UNIQUE",
    "CREATE CONSTRAINT applicant_name_v2 IF NOT EXISTS FOR (n:Applicant) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT ipc_code_v2 IF NOT EXISTS FOR (n:IPC) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT technology_name_v2 IF NOT EXISTS FOR (n:Technology) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT domain_name_v2 IF NOT EXISTS FOR (n:Domain) REQUIRE n.name IS UNIQUE",
]
INDEXES = [
    "CREATE INDEX patent_apply_year_v2 IF NOT EXISTS FOR (n:Patent) ON (n.apply_year)",
    "CREATE INDEX patent_country_v2 IF NOT EXISTS FOR (n:Patent) ON (n.country)",
]

NODE_QUERIES = {
    "Patent": """
        UNWIND $rows AS row
        MERGE (n:Patent {patent_id: row.patent_id})
        SET n.title = row.title, n.abstract = row.abstract,
            n.apply_date = row.apply_date, n.apply_year = row.apply_year,
            n.pub_date = row.pub_date, n.patent_type = row.patent_type,
            n.country = row.country, n.legal_status = row.legal_status,
            n.is_in_sample = row.is_in_sample
    """,
    "Applicant": """
        UNWIND $rows AS row
        MERGE (n:Applicant {name: row.name})
        SET n.raw_names = row.raw_names, n.type = row.type, n.country = row.country
    """,
    "IPC": """
        UNWIND $rows AS row
        MERGE (n:IPC {code: row.code})
        SET n.name = row.name, n.level = row.level
    """,
    "Technology": """
        UNWIND $rows AS row
        MERGE (n:Technology {name: row.name})
        SET n.keywords = row.keywords, n.description = row.description
    """,
    "Domain": """
        UNWIND $rows AS row
        MERGE (n:Domain {name: row.name})
        SET n.description = row.description
    """,
}

REL_QUERIES = {
    "APPLIES_FOR": """
        UNWIND $rows AS row
        MATCH (a:Applicant {name: row.name})
        MATCH (p:Patent {patent_id: row.patent_id})
        CREATE (a)-[:APPLIES_FOR {is_first: row.is_first}]->(p)
    """,
    "CITES": """
        UNWIND $rows AS row
        MATCH (c:Patent {patent_id: row.citing_id})
        MATCH (d:Patent {patent_id: row.cited_id})
        CREATE (c)-[:CITES]->(d)
    """,
    "HAS_IPC": """
        UNWIND $rows AS row
        MATCH (p:Patent {patent_id: row.patent_id})
        MATCH (i:IPC {code: row.ipc_code})
        CREATE (p)-[:HAS_IPC {is_main: row.is_main}]->(i)
    """,
    "INVOLVES": """
        UNWIND $rows AS row
        MATCH (p:Patent {patent_id: row.patent_id})
        MATCH (t:Technology {name: row.topic})
        CREATE (p)-[:INVOLVES]->(t)
    """,
    "BELONGS_TO": """
        UNWIND $rows AS row
        MATCH (t:Technology {name: row.topic})
        MATCH (d:Domain {name: row.domain})
        CREATE (t)-[:BELONGS_TO]->(d)
    """,
    "CO_APPLIED_WITH": """
        UNWIND $rows AS row
        MATCH (a:Applicant {name: row.app_a})
        MATCH (b:Applicant {name: row.app_b})
        CREATE (a)-[:CO_APPLIED_WITH {weight: row.weight}]->(b)
    """,
}


def _none(value):
    return None if pd.isna(value) else value


def _bool(value):
    return None if pd.isna(value) else bool(value)


def _mode(values: pd.Series):
    values = values.dropna().astype(str)
    values = values[values.str.strip() != ""]
    return values.value_counts().index[0] if len(values) else None


def _batch(session, query, rows, size, label):
    total = len(rows)
    started = time.time()
    for start in range(0, total, size):
        chunk = rows[start:start + size]
        session.execute_write(lambda tx, c=chunk: tx.run(query, rows=c).consume())
        done = min(start + size, total)
        print(f"  {label}: {done:,}/{total:,} ({time.time() - started:.0f}s)", flush=True)


def _counts(session):
    nodes = {label: session.run(f"MATCH (n:{label}) RETURN count(n) AS n").single()["n"]
             for label in NODES}
    rels = {rel: session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n").single()["n"]
            for rel in RELS}
    return nodes, rels


def _server_info(session):
    rows = session.run(
        "CALL dbms.components() YIELD name, versions, edition "
        "RETURN name, versions, edition").data()
    kernel = next((row for row in rows if row["name"] == "Neo4j Kernel"), None)
    if not kernel:
        return "unknown", "unknown"
    return kernel["versions"][0], kernel["edition"]


def _clear_contract(session):
    labels = " OR ".join(f"n:{label}" for label in NODES)
    session.run(f"MATCH (n) WHERE {labels} DETACH DELETE n").consume()


def _load_rows(processed: Path):
    tables = {name: pd.read_parquet(processed / f"{name}.parquet") for name in TABLE_COLUMNS}

    patents = tables["patents"]
    patent_rows = [{
        "patent_id": r.patent_id,
        "title": _none(r.title),
        "abstract": _none(r.abstract),
        "apply_date": _none(r.apply_date),
        "apply_year": None if pd.isna(r.apply_year) else int(r.apply_year),
        "pub_date": _none(r.pub_date),
        "patent_type": _none(r.patent_type),
        "country": _none(r.country),
        "legal_status": _none(r.legal_status),
        "is_in_sample": bool(r.is_in_sample),
    } for r in patents.itertuples()]

    applicants = tables["applicants"]
    grouped = applicants.groupby("applicant_std", dropna=False)
    applicant_rows = []
    for name, group in grouped:
        raw = sorted({str(x) for x in group["applicant_raw"].dropna() if str(x).strip()})
        applicant_rows.append({
            "name": str(name),
            "raw_names": raw,
            "type": _mode(group["applicant_type"]),
            "country": None,
        })

    ipc = tables["patent_ipc"]
    ipc_rows = [{"code": str(code), "name": None,
                 "level": "subclass" if len(str(code)) <= 4 else "group"}
                for code in sorted(ipc["ipc_code"].dropna().astype(str).unique())]

    topic = tables["patent_topic"]
    technology_rows = [{"name": str(name), "keywords": [], "description": None}
                       for name in sorted(topic["topic"].dropna().astype(str).unique())]
    domain_rows = [{"name": str(name), "description": None}
                   for name in sorted(topic["domain"].dropna().astype(str).unique())]

    applies_rows = [{
        "name": str(r.applicant_std), "patent_id": r.patent_id, "is_first": _bool(r.is_first),
    } for r in applicants.itertuples()]
    citations = tables["citations"]
    cite_rows = [{"citing_id": r.citing_id, "cited_id": r.cited_id}
                 for r in citations[citations["cited_in_sample"]].itertuples()]
    ipc_rel_rows = [{"patent_id": r.patent_id, "ipc_code": str(r.ipc_code), "is_main": _bool(r.is_main)}
                    for r in ipc.itertuples()]
    involves_rows = [{"patent_id": r.patent_id, "topic": str(r.topic)} for r in topic.itertuples()]
    belongs_rows = [{"topic": str(r.topic), "domain": str(r.domain)}
                    for r in topic[["topic", "domain"]].drop_duplicates().itertuples()]
    co = tables["cooperation"]
    co_rows = [{"app_a": str(r.app_a), "app_b": str(r.app_b), "weight": int(r.weight)}
               for r in co.itertuples()]

    return {
        "nodes": {
            "Patent": patent_rows, "Applicant": applicant_rows, "IPC": ipc_rows,
            "Technology": technology_rows, "Domain": domain_rows,
        },
        "rels": {
            "APPLIES_FOR": applies_rows, "CITES": cite_rows, "HAS_IPC": ipc_rel_rows,
            "INVOLVES": involves_rows, "BELONGS_TO": belongs_rows, "CO_APPLIED_WITH": co_rows,
        },
        "source_counts": {
            "patents": len(patents), "applicants": len(applicants),
            "applicant_names": applicants["applicant_std"].nunique(),
            "ipc": ipc["ipc_code"].nunique(), "topics": topic["topic"].nunique(),
            "domains": topic["domain"].nunique(),
            "topic_domain_pairs": len(topic[["topic", "domain"]].drop_duplicates()),
            "citations_all": len(citations),
            "citations_in_sample": int(citations["cited_in_sample"].sum()),
            "citations_external": int((~citations["cited_in_sample"]).sum()),
            "cooperation": len(co),
        },
    }


def _query_samples(session, top_applicant: str):
    queries = [
        ("申请量 Top 10", """
            MATCH (a:Applicant)-[:APPLIES_FOR]->(p:Patent)
            RETURN a.name AS 申请人, count(DISTINCT p) AS 专利数
            ORDER BY 专利数 DESC, 申请人 LIMIT 10
        """),
        ("企业 → IPC", """
            MATCH (a:Applicant {name: $name})-[:APPLIES_FOR]->(:Patent)-[:HAS_IPC]->(i:IPC)
            RETURN i.code AS IPC, count(*) AS 专利数
            ORDER BY 专利数 DESC, IPC LIMIT 10
        """),
        ("企业 → 技术主题 → 领域", """
            MATCH (a:Applicant {name: $name})-[:APPLIES_FOR]->(:Patent)
                  -[:INVOLVES]->(t:Technology)-[:BELONGS_TO]->(d:Domain)
            RETURN d.name AS 领域, t.name AS 主题, count(*) AS 专利数
            ORDER BY 专利数 DESC, 领域, 主题 LIMIT 10
        """),
    ]
    out = []
    for title, cypher in queries:
        rows = session.run(cypher, name=top_applicant).data()
        out.append({"title": title, "cypher": cypher.strip(), "params": {"name": top_applicant},
                    "rows": rows})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="import data/_sample instead of processed")
    parser.add_argument("--reset", action="store_true", help="delete existing contract-A nodes first")
    parser.add_argument("--node-batch", type=int, default=5000)
    parser.add_argument("--rel-batch", type=int, default=10000)
    args = parser.parse_args()

    processed = (config.DATA_DIR / "_sample") if args.sample else config.PROCESSED_DIR
    if not (processed / "patents.parquet").is_file():
        raise SystemExit(f"missing {processed / 'patents.parquet'}")
    if not config.NEO4J_PASSWORD:
        raise SystemExit("set NEO4J_PASSWORD in .env first")

    data = _load_rows(processed)
    driver = GraphDatabase.driver(config.NEO4J_URI,
                                  auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    started = time.time()
    with driver.session(database="neo4j") as session:
        session.run("RETURN 1").consume()
        existing = session.run("MATCH (n) WHERE " + " OR ".join(f"n:{x}" for x in NODES) +
                               " RETURN count(n) AS n").single()["n"]
        if existing and not args.reset:
            raise SystemExit(f"contract graph already has {existing:,} nodes; pass --reset to rebuild")
        if existing:
            print(f"clearing {existing:,} contract nodes", flush=True)
            _clear_contract(session)

        for statement in CONSTRAINTS + INDEXES:
            session.run(statement).consume()
        session.run("CALL db.awaitIndexes(300)").consume()

        for label in NODES:
            print(f"import {label}", flush=True)
            _batch(session, NODE_QUERIES[label], data["nodes"][label],
                   args.node_batch, label)
        for rel in RELS:
            print(f"import {rel}", flush=True)
            _batch(session, REL_QUERIES[rel], data["rels"][rel],
                   args.rel_batch, rel)

        actual_nodes, actual_rels = _counts(session)
        expected_nodes = {k: len(v) for k, v in data["nodes"].items()}
        expected_rels = {k: len(v) for k, v in data["rels"].items()}
        if actual_nodes != expected_nodes:
            raise SystemExit(f"node count mismatch: {actual_nodes} != {expected_nodes}")
        if actual_rels != expected_rels:
            raise SystemExit(f"relationship count mismatch: {actual_rels} != {expected_rels}")

        top = session.run("""
            MATCH (a:Applicant)-[:APPLIES_FOR]->(p:Patent)
            RETURN a.name AS name, count(DISTINCT p) AS n
            ORDER BY n DESC, name LIMIT 1
        """).single()
        top_applicant = top["name"]
        samples = _query_samples(session, top_applicant)
        constraints = session.run(
            "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties "
            "RETURN name, type, labelsOrTypes, properties ORDER BY name").data()
        indexes = session.run(
            "SHOW INDEXES YIELD name, type, labelsOrTypes, properties "
            "RETURN name, type, labelsOrTypes, properties ORDER BY name").data()
        neo4j_version, neo4j_edition = _server_info(session)

    driver.close()

    scope = "sample" if args.sample else "full"
    scale = {
        "status": "ok",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": scope,
        "source": str(processed.relative_to(config.ROOT_DIR)).replace("\\", "/"),
        "neo4j": {"uri": config.NEO4J_URI, "version": neo4j_version,
                  "edition": neo4j_edition},
        "nodes": actual_nodes,
        "relationships": actual_rels,
        "source_counts": data["source_counts"],
        "not_imported": {
            "external_citations": data["source_counts"]["citations_external"],
            "reason": "CITES only imports cited_in_sample=true; external targets use external_citation_applicants.parquet",
        },
        "constraints": constraints,
        "indexes": indexes,
        "verification": {
            "nodes_match_parquet": actual_nodes == expected_nodes,
            "relationships_match_parquet": actual_rels == expected_rels,
        },
        "query_samples": samples,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    out_name = "scale_sample.json" if args.sample else "scale.json"
    out_path = config.RESULTS_DIR / out_name
    out_path.write_text(json.dumps(scale, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    delivery = config.ROOT_DIR / "交付给同伴的内容" / "P1-7_图谱建图"
    delivery.mkdir(parents=True, exist_ok=True)
    (delivery / out_name).write_text(
        json.dumps(scale, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sample_lines = []
    for item in samples:
        sample_lines.append(f"### {item['title']}\n\n```cypher\n{item['cypher']}\n```\n")
        sample_lines.append("| " + " | ".join(item["rows"][0].keys()) + " |")
        sample_lines.append("|" + "---|" * len(item["rows"][0]))
        for row in item["rows"][:10]:
            sample_lines.append("| " + " | ".join(str(v) for v in row.values()) + " |")
        sample_lines.append("")
    (delivery / "查询样例.md").write_text(
        "# P1-7 查询样例\n\n" + "\n".join(sample_lines), encoding="utf-8")

    readme = f"""# P1-7 Neo4j 图谱建图

生成时间：{scale['generated_at']}
数据源：`{scale['source']}`；Neo4j {scale['neo4j']['version']} {scale['neo4j']['edition']}，`{config.NEO4J_URI}`。

## 规模

| 节点 | 数量 |
|---|---:|
""" + "\n".join(f"| `{k}` | {v:,} |" for k, v in actual_nodes.items()) + """

| 关系 | 数量 |
|---|---:|
""" + "\n".join(f"| `{k}` | {v:,} |" for k, v in actual_rels.items()) + f"""

- 校验：节点/关系计数与 parquet **全部一致**。
- CITES 只导入样本内 {data['source_counts']['citations_in_sample']:,} 条；外部 {data['source_counts']['citations_external']:,} 条不建占位节点，企业级分析用 `external_citation_applicants.parquet`。
- 约束/索引清单见 `scale.json`。

## 复现

```bash
python -m scripts.build_graph          # 全量
python -m scripts.build_graph --sample # 样例（会要求 --reset）
python -m scripts.build_graph --reset  # 重建前清空契约图
```

Neo4j 需先启动，`.env` 配置 `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`。5.26 的 Windows 启动脚本在含中文的路径下会路径解析失败，建议把 Neo4j 解压到纯英文路径（本机：`C:\\Users\\Lenovo\\neo4j-community-5.26.0`）。

## 口径

- `Patent` 包含全部 {data['source_counts']['patents']:,} 件，含外观设计；外观设计只有 `APPLIES_FOR` / `CITES`，没有 `HAS_IPC` / `INVOLVES`。
- `Applicant` 是标准化申请人 {data['source_counts']['applicant_names']:,} 个，展示层别名合并尚未在此图执行。
- `IPC` 只有代码；`name` 为空，`level` 由代码长度推断（4 位=subclass，其余=group）。
- `Technology` 50 个、`Domain` 8 个，来自规则主题表；`keywords` / `description` 暂空。
- `Applicant.country` 暂空：七表没有申请人国家字段，不伪造。
- `CO_APPLIED_WITH` 每对只建一条有向边（名称排序），查询时按无向匹配。
"""
    (delivery / "说明.md").write_text(readme, encoding="utf-8")

    print(json.dumps({
        "scope": scope, "nodes": actual_nodes, "relationships": actual_rels,
        "elapsed_seconds": scale["elapsed_seconds"], "output": str(out_path),
        "top_applicant": top_applicant,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
