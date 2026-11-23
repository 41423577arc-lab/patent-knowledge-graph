# -*- coding: utf-8 -*-
"""重载企业节点与 APPLIED 关系（清洗后）。"""
import csv
from pathlib import Path
from neo4j import GraphDatabase

D = Path(__file__).resolve().parent / "data"
drv = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", "kgpatent2026"))

def rows(name):
    with open(D / name, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)

def chunks(it, n=4000):
    buf = []
    for r in it:
        buf.append(r)
        if len(buf) >= n:
            yield buf; buf = []
    if buf:
        yield buf

with drv.session() as s:
    s.run("MATCH (c:Company) DETACH DELETE c").consume()
    s.run("CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE").consume()
    total = 0
    for b in chunks(rows("companies.csv")):
        s.run("UNWIND $rows AS r MERGE (:Company {name: r.name})", rows=b).consume()
        total += len(b)
    print("companies", total)
    total = 0
    for b in chunks(rows("rel_applied.csv")):
        s.run("""UNWIND $rows AS r
                 MATCH (c:Company {name: r.company}) MATCH (p:Patent {id: r.patent_id})
                 MERGE (c)-[:APPLIED]->(p)""", rows=b).consume()
        total += len(b)
    print("applied", total)
    print(s.run("MATCH (c:Company) RETURN count(c) AS n").single()["n"])
drv.close()
