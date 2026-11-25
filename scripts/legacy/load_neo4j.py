# -*- coding: utf-8 -*-
"""把 kg_system/data 下的 CSV 导入 Neo4j（批量 UNWIND，无需 APOC）。"""
import csv, os, sys
from pathlib import Path
from neo4j import GraphDatabase

from core.config import NEO4J_URI as URI, NEO4J_USER as USER, NEO4J_PASSWORD as PWD
DATA = Path(__file__).resolve().parents[2] / "data" / "legacy"

CONSTRAINTS = [
    "CREATE CONSTRAINT patent_id IF NOT EXISTS FOR (p:Patent) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT class_code IF NOT EXISTS FOR (t:TechClass) REQUIRE t.code IS UNIQUE",
    "CREATE CONSTRAINT inventor_name IF NOT EXISTS FOR (i:Inventor) REQUIRE i.name IS UNIQUE",
]


def rows(name):
    with open(DATA / name, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def batches(it, n=4000):
    buf = []
    for r in it:
        buf.append(r)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def to_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def main():
    drv = GraphDatabase.driver(URI, auth=(USER, PWD))
    with drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n").consume()
        for c in CONSTRAINTS:
            s.run(c).consume()
        print("schema ready")

        def run_batches(cypher, name, conv=None):
            total = 0
            for b in batches(rows(name)):
                if conv:
                    b = [conv(r) for r in b]
                s.run(cypher, rows=b).consume()
                total += len(b)
            print("%-22s %7d" % (name, total))
            return total

        run_batches(
            """UNWIND $rows AS r
               MERGE (p:Patent {id: r.id})
               SET p.title = r.title, p.date = r.date, p.year = toInteger(r.year),
                   p.ipc_main = r.ipc_main, p.class4 = r.class4, p.legal = r.legal,
                   p.is_granted = toInteger(r.is_granted), p.is_rejected = toInteger(r.is_rejected),
                   p.label = r.label, p.n_cited = toInteger(r.n_cited), p.is_stub = false""",
            "patents.csv")

        run_batches(
            """UNWIND $rows AS r
               MERGE (p:Patent {id: r.id})
               ON CREATE SET p.is_stub = true
               SET p.stub_n_cited = toInteger(r.n_cited)""",
            "stub_patents.csv")

        run_batches(
            "UNWIND $rows AS r MERGE (c:Company {name: r.name})",
            "companies.csv")

        run_batches(
            """UNWIND $rows AS r
               MERGE (t:TechClass {code: r.code})
               SET t.sector = r.sector, t.n = toInteger(r.n)""",
            "classes.csv")

        run_batches(
            """UNWIND $rows AS r
               MATCH (c:Company {name: r.company}) MATCH (p:Patent {id: r.patent_id})
               MERGE (c)-[:APPLIED]->(p)""",
            "rel_applied.csv")

        run_batches(
            """UNWIND $rows AS r
               MERGE (i:Inventor {name: r.inventor})
               WITH i, r MATCH (p:Patent {id: r.patent_id})
               MERGE (i)-[:INVENTED]->(p)""",
            "rel_invented.csv")

        run_batches(
            """UNWIND $rows AS r
               MATCH (p:Patent {id: r.patent_id}) MATCH (t:TechClass {code: r.class4})
               MERGE (p)-[:IN_CLASS]->(t)""",
            "rel_in_class.csv")

        run_batches(
            """UNWIND $rows AS r
               MATCH (a:Patent {id: r.citing}) MATCH (b:Patent {id: r.cited})
               MERGE (a)-[e:CITES]->(b)
               SET e.cited_is_stub = toInteger(r.cited_is_stub)""",
            "rel_cites.csv")

        counts = s.run("""MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC""").data()
        for c in counts:
            print("  %-12s %d" % (c["label"], c["n"]))
        rels = s.run("""MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY n DESC""").data()
        for r in rels:
            print("  %-12s %d" % (r["t"], r["n"]))
    drv.close()


if __name__ == "__main__":
    main()

