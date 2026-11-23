# -*- coding: utf-8 -*-
"""ETL: incoPat patent xlsx -> knowledge-graph CSVs (patents/companies/classes/relations)."""
import csv, json, re, zipfile
from pathlib import Path
from lxml import etree

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

COLS = {
    "B": "title", "F": "applicants_raw", "BA": "applicants_std",
    "G": "pub_no", "H": "pub_date", "J": "app_date", "DX": "priority_date",
    "K": "pub_type", "AF": "ipc_main", "BW": "inventors",
    "CK": "cites", "CL": "cited_by", "EG": "legal",
    "CW": "n_cites", "CX": "n_cited",
}

SECTOR = {
    "H01M": "电池", "H01G": "电池", "H02J": "充换电",
    "H02K": "电机", "H02P": "电机",
    "B60L": "电控/驱动", "B60W": "电控/驱动", "B60R": "电控/驱动", "B60T": "电控/驱动",
    "B60K": "整车/动力", "B62D": "整车/动力", "B60H": "热管理",
    "G01R": "测试验证", "G06F": "软件/算法", "G05B": "软件/算法", "G06Q": "软件/算法",
}

def sector_of(code4):
    return SECTOR.get(code4, "其他")

def read_shared_strings(z):
    try:
        with z.open("xl/sharedStrings.xml") as fh:
            out = []
            for ev, el in etree.iterparse(fh, events=("end",), tag=NS + "si"):
                out.append("".join(t.text or "" for t in el.iter(NS + "t")))
                el.clear()
            return out
    except KeyError:
        return []

def cell_text(c, shared):
    t = c.get("t")
    if t == "s":
        v = c.find(NS + "v")
        if v is None or v.text is None:
            return ""
        try:
            return shared[int(v.text)]
        except Exception:
            return ""
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter(NS + "t"))
    v = c.find(NS + "v")
    return v.text if v is not None and v.text is not None else ""

def to_iso(v):
    if not v:
        return ""
    v = v.strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    if re.fullmatch(r"\d{5}(\.0+)?", v):
        from datetime import datetime, timedelta
        d = datetime(1899, 12, 30) + timedelta(days=float(v))
        return d.strftime("%Y-%m-%d")
    return v[:10]

def split_multi(s, limit=8):
    if not s:
        return []
    parts = re.split(r"[;；|]", str(s))
    seen, out = set(), []
    for p in parts:
        p = p.strip()
        if p and p not in seen and len(p) < 200:
            seen.add(p)
            out.append(p)
        if len(out) >= limit:
            break
    return out

def clean_name(n):
    n = (n or "").strip().strip("[]").strip()
    n = re.sub(r"-[A-Z]{1,2}\]?$", "", n)
    return n.strip("[]").strip()


def iter_rows(xlsx, stride, cap, shared):
    z = zipfile.ZipFile(xlsx)
    shared = shared or read_shared_strings(z)
    with z.open("xl/worksheets/sheet1.xml") as fh:
        buf = {}
        idx = 0
        for ev, el in etree.iterparse(fh, events=("end",), tag=NS + "row"):
            idx += 1
            if idx > 1 and (idx - 1) % stride == 0:
                row = {}
                for c in el.iter(NS + "c"):
                    ref = c.get("r") or ""
                    col = re.match(r"([A-Z]+)", ref)
                    if not col:
                        continue
                    letter = col.group(1)
                    if letter in COLS:
                        row[COLS[letter]] = cell_text(c, shared)
                if row:
                    yield row
                if idx > cap * stride:
                    el.clear()
                    break
            el.clear()

def main():
    files = [
        ("data/patent/train/positive/2025-08-07-10.xlsx", "positive"),
        
        ("data/patent/train/negative/2025-08-07.xlsx", "negative"),
        ("data/patent/train/negative/2025-08-07-2.xlsx", "negative"),
    ]
    out = Path("kg_system/data")
    out.mkdir(parents=True, exist_ok=True)

    patents, companies, classes = {}, {}, {}
    rel_applied, rel_invented, rel_in_class = [], [], []
    raw_cites = []
    stats = {"files": {}, "rows_seen": 0, "rows_kept": 0}

    stride = 1
    cap = 40000  # per file

    for path, label in files:
        p = Path(path)
        if not p.exists():
            print("MISSING", path)
            continue
        kept = 0
        try:
            z0 = zipfile.ZipFile(p)
        except Exception as e:
            print("SKIP broken file:", path, e)
            stats["files"][path] = "broken"
            continue
        shared = read_shared_strings(z0)
        z0.close()
        for row in iter_rows(p, stride, cap, shared):
            pid = (row.get("pub_no") or "").strip()
            if not pid:
                continue
            kept += 1
            title = (row.get("title") or "").strip()
            legal = (row.get("legal") or "").strip()
            ipc_main = (row.get("ipc_main") or "").strip()
            code4 = ipc_main[:4] if len(ipc_main) >= 4 else ipc_main
            date = to_iso(row.get("pub_date")) or to_iso(row.get("app_date")) or to_iso(row.get("priority_date"))
            applicants = [clean_name(x) for x in (split_multi(row.get("applicants_raw")) or split_multi(row.get("applicants_std")))]
            applicants = [x for x in applicants if x]
            inventors = split_multi(row.get("inventors"), 10)

            if pid not in patents:
                patents[pid] = {
                    "id": pid, "title": title[:300], "date": date,
                    "year": date[:4] if date else "",
                    "ipc_main": ipc_main, "class4": code4,
                    "legal": legal,
                    "is_granted": 1 if "授权" in legal else 0,
                    "is_rejected": 1 if "驳回" in legal else 0,
                    "label": label,
                    "n_cited": (row.get("n_cited") or "0").split(".")[0],
                }
            for a in applicants:
                companies.setdefault(a, {"name": a, "n": 0})["n"] += 1
                rel_applied.append((pid, a))
            for inv in inventors:
                rel_invented.append((pid, inv))
            if code4:
                classes.setdefault(code4, {"code": code4, "sector": sector_of(code4), "n": 0})["n"] += 1
                rel_in_class.append((pid, code4))
            for c in split_multi(row.get("cites"), 12):
                raw_cites.append((pid, c.upper(), 1))
            for c in split_multi(row.get("cited_by"), 12):
                raw_cites.append((c.upper(), pid, 1))
        stats["files"][path] = kept
        stats["rows_kept"] += kept
        print("done", path, kept, flush=True)

    # dedupe cites, keep only clean ids
    cite_set = set()
    for a, b, _ in raw_cites:
        if a and b and a != b and len(a) < 40 and len(b) < 40:
            cite_set.add((a, b))

    stub = {}
    rel_cites = []
    for a, b in cite_set:
        if a not in patents:
            continue
        if b in patents:
            rel_cites.append((a, b, 0))
        else:
            stub.setdefault(b, 0)
            stub[b] += 1
            rel_cites.append((a, b, 1))

    # write
    def wcsv(name, header, rows):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    wcsv("patents.csv",
         ["id", "title", "date", "year", "ipc_main", "class4", "legal",
          "is_granted", "is_rejected", "label", "n_cited"],
         [[p["id"], p["title"], p["date"], p["year"], p["ipc_main"], p["class4"],
           p["legal"], p["is_granted"], p["is_rejected"], p["label"], p["n_cited"]]
          for p in patents.values()])
    wcsv("companies.csv", ["name"], [[c] for c in companies])
    wcsv("classes.csv", ["code", "sector", "n"],
         [[c["code"], c["sector"], c["n"]] for c in classes.values()])
    wcsv("rel_applied.csv", ["patent_id", "company"], rel_applied)
    wcsv("rel_invented.csv", ["patent_id", "inventor"], rel_invented)
    wcsv("rel_in_class.csv", ["patent_id", "class4"], rel_in_class)
    wcsv("rel_cites.csv", ["citing", "cited", "cited_is_stub"], rel_cites)
    wcsv("stub_patents.csv", ["id", "n_cited"], [[k, v] for k, v in stub.items()])

    stats.update({
        "patents": len(patents), "companies": len(companies),
        "classes": len(classes), "inventors": len({i for _, i in rel_invented}),
        "rel_applied": len(rel_applied), "rel_invented": len(rel_invented),
        "rel_in_class": len(rel_in_class), "rel_cites": len(rel_cites),
        "stub_patents": len(stub),
        "granted": sum(p["is_granted"] for p in patents.values()),
        "rejected": sum(p["is_rejected"] for p in patents.values()),
    })
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

