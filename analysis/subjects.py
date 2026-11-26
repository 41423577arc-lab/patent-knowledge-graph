"""P3 scope adapter. P2 owns accepted aliases; P1 metrics are never merged."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from core import config
from qa import auxiliary
from analysis.membership import member_of


def _verified(path, manifest):
    """Match auxiliary bytes to the already established immutable local delivery."""
    provenance=manifest.get("local_provenance", {})
    root=Path(provenance.get("source_directory", ""))
    if not provenance.get("source_commit") or not root.is_dir():
        raise ValueError("缺少辅助表的固定交付来源，保留原始主体口径")
    source=json.loads((root.parent/"source_manifest.json").read_text(encoding="utf-8"))
    if source["commit"]!=provenance["source_commit"]:
        raise ValueError("辅助表与指标的固定来源版本不同")
    expected=[r for r in source["files"] if Path(r["path"]).name==path.name and "/P1-8_" in r["path"]]
    if len(expected)!=1 or hashlib.sha256(path.read_bytes()).hexdigest()!=expected[0].get("sha256"):
        raise ValueError(f"{path.name} 与固定交付的内容签名不一致")


def build_index(tables, aliases, alias_rows, delivered_counts=None, delivered_cooperation=None, *, sample=False):
    """Only exact one-hop aliases, exactly as Catalog.members; all counts use sets."""
    approved=alias_rows.loc[alias_rows["method"].isin(["manual","auto_en"])]
    approved=approved.loc[approved["alias"].ne("") & approved["canonical"].ne("")]
    conflicts=set(approved.groupby("alias")["canonical"].nunique().loc[lambda x:x>1].index)
    pending=set(alias_rows.loc[alias_rows["method"].eq("pending_review"),"alias"])
    blocked=conflicts|pending
    mapping={a:c for a,c in aliases.items() if isinstance(a,str) and isinstance(c,str) and a and c and a not in blocked and c not in blocked}
    patents=tables["patents"]
    ids=set(patents.loc[patents["is_in_sample"].fillna(False),"patent_id"])
    owners=tables["applicants"][["patent_id","applicant_std"]].dropna().drop_duplicates()
    owners=owners.loc[member_of(owners["patent_id"],ids) & owners["applicant_std"].ne("")].copy()
    owners["canonical"]=owners["applicant_std"].map(lambda n:mapping.get(n,n))
    raw_sets=defaultdict(set);merged_sets=defaultdict(set);member_sets=defaultdict(set)
    for pid,std,canonical in owners[["patent_id","applicant_std","canonical"]].itertuples(index=False,name=None):
        raw_sets[std].add(pid);merged_sets[canonical].add(pid);member_sets[canonical].add(std)
    raw={n:frozenset(v) for n,v in raw_sets.items()}
    merged={n:frozenset(v) for n,v in merged_sets.items()}
    members={n:tuple(sorted(v)) for n,v in member_sets.items()}
    trace=owners[["applicant_std","canonical"]].drop_duplicates().sort_values(["canonical","applicant_std"])
    counts=pd.DataFrame([(n,len(s)) for n,s in merged.items()],columns=["applicant_std","patent_count"])
    count_differences=[]
    if delivered_counts is not None:
        if not {"canonical","patent_count"}<=set(delivered_counts) or delivered_counts["canonical"].duplicated().any():
            raise ValueError("主体申请量辅助表结构或唯一性不符合交付")
        check=counts.set_index("applicant_std").rename(columns={"patent_count":"patent_count_actual"}).join(
            delivered_counts.set_index("canonical")[["patent_count"]].rename(columns={"patent_count":"patent_count_p1"}),how="outer")
        count_differences=check.loc[check["patent_count_actual"].ne(check["patent_count_p1"])].reset_index().to_dict("records")
    # Candidate pairs come only from the current contract, never a Cartesian product.
    contributions=defaultdict(list)
    self_edges=0
    for r in tables["cooperation"].itertuples():
        a,b=mapping.get(r.app_a,r.app_a),mapping.get(r.app_b,r.app_b)
        if a==b:
            self_edges+=1
            continue
        contributions[tuple(sorted((a,b)))].append((r.app_a,r.app_b,int(r.weight)))
    candidates={pair:sum(r[2] for r in rows) for pair,rows in contributions.items()}
    if delivered_cooperation is not None:
        if delivered_cooperation.duplicated(["app_a","app_b"]).any():
            raise ValueError("合并合作表存在重复主体对")
        supplied={tuple(sorted((r.app_a,r.app_b))):r.weight for r in delivered_cooperation.itertuples()}
        all_pairs=set(candidates)|set(supplied)
    else:
        supplied=candidates;all_pairs=set(candidates)
    edges=[];corrections=[];skipped=[]
    for a,b in sorted(all_pairs):
        pair=(a,b);weight=supplied.get(pair)
        reason=None
        if a==b or a in blocked or b in blocked: reason="自合作或名称待确认/冲突，未作为有效合并合作展示"
        elif a not in merged or b not in merged: reason="主体不在当前专利范围"
        elif weight is None or not pd.notna(weight) or weight!=candidates.get(pair) or float(weight)<=0:
            reason="P1 边权与当前原始合作贡献不匹配"
        evidence=merged.get(a,frozenset()) & merged.get(b,frozenset())
        parts=contributions.get(pair,[])
        union=set()
        for x,y,w in parts:
            subset=raw.get(x,frozenset()) & raw.get(y,frozenset())
            if len(subset)!=w: reason="原始契约边权与真实专利交集不一致"
            union.update(subset)
        if not evidence or union!=evidence: reason=reason or "原始合作证据不能覆盖合并交集"
        if reason:
            skipped.append({"app_a":a,"app_b":b,"reason":reason})
            continue
        actual=len(evidence)
        if weight!=actual:
            corrections.append({"app_a":a,"app_b":b,"p1_weight":int(weight),"evidence_count":actual,
                                "reason":"多个原始主体对共享同一专利，P1 累加权重重复计数",
                                "raw_pairs":[{"app_a":x,"app_b":y,"weight":w} for x,y,w in parts]})
        edges.append((a,b,actual,int(weight)))
    network=pd.DataFrame(edges,columns=["app_a","app_b","weight","p1_weight"])
    return {"available":True,"aliases":mapping,"pending":pending,"conflicts":conflicts,
            "members":members,"raw_patents":raw,"patents":merged,"trace":trace,"counts":counts,
            "cooperation":network,"corrections":corrections,"skipped_edges":skipped,"self_edges_removed":self_edges,
            "count_differences":count_differences,"sample":sample,"note":"与 P2 相同的已确认单跳映射；当前专利集合去重，原始表未修改。"}


def load_index(tables, manifest):
    try:
        alias_path=config.RESULTS_DIR/"company_alias.csv"
        _verified(alias_path,manifest)
        # Delegate the accepted mapping policy to P2. Metadata is read only for
        # pending/conflict disclosure; no separate fuzzy/normalization engine.
        aliases=auxiliary.aliases()
        rows=pd.read_csv(alias_path,keep_default_na=False)
        counts=cooperation=None
        if not config.USE_SAMPLE:
            for name in ["company_patent_counts.csv","cooperation_merged.parquet"]:
                _verified(config.RESULTS_DIR/name,manifest)
            counts=pd.read_csv(config.RESULTS_DIR/"company_patent_counts.csv")
            cooperation=auxiliary.merged_cooperation()
        return build_index(tables,aliases,rows,counts,cooperation,sample=config.USE_SAMPLE)
    except (OSError,ValueError,KeyError,TypeError,auxiliary.DataUnavailable) as exc:
        return {"available":False,"note":f"确认别名展示不可用，使用原始契约口径：{exc}"}
