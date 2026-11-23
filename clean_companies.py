# -*- coding: utf-8 -*-
"""清洗企业名：去掉 incoPat 标准化申请人的方括号与国家码后缀，合并重复实体。"""
import csv, re, shutil
from pathlib import Path

D = Path("kg_system/data")

def clean(n):
    n = (n or "").strip().strip("[]").strip()
    n = re.sub(r"-[A-Z]{1,2}\]?$", "", n)
    return n.strip("[]").strip()

with open(D / "companies.csv", encoding="utf-8") as f:
    names = {clean(r["name"]) for r in csv.DictReader(f)}
names.discard("")

rows = []
with open(D / "rel_applied.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        n = clean(r["company"])
        if n:
            rows.append((r["patent_id"], n))

with open(D / "companies.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["name"])
    for n in sorted(names):
        w.writerow([n])

with open(D / "rel_applied.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["patent_id", "company"])
    w.writerows(rows)

print("companies", len(names), "applied", len(rows))
