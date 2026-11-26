"""Run the frozen development corpus on the 481-patent sample graph."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import sys
from time import perf_counter
from unittest.mock import patch

from core import config
from core.data_loader import load_result, load_table
from qa import auxiliary, intents as I, llm_client
from qa.service import answer
from qa.tests.stage2_cases import BOUNDARIES, CASES


def check_evidence(result, case, tables, metrics, yearly):
    """Check principal facts against P1 inputs, independent of returned prose."""
    intent = case["intent"]
    rows, slots = result["data"], result["slots"]
    patents, applicants, tags, cites, ipc, coop, external = tables
    window = patents if "start_year" not in slots else patents[patents.apply_year.between(slots["start_year"], slots["end_year"])]
    source = set(applicants.loc[applicants.applicant_std.eq(case["entity"]), "patent_id"]) & set(window.patent_id)
    subject_data = applicants[applicants.patent_id.isin(window.patent_id)]
    enterprise = set()
    if slots.get("subject_scope") == "enterprise":
        for name, group in applicants.groupby("applicant_std", sort=False):
            ranks = Counter(value for value in group.applicant_type.dropna() if value.strip())
            if ranks and ranks.most_common(1)[0][0] == "企业":
                enterprise.add(name)
    if slots.get("subject_scope") == "enterprise":
        subject_data = subject_data[subject_data.applicant_std.isin(enterprise)]
    graph = result["graph"]
    ids = {n["id"] for n in graph["nodes"]}
    assert len(ids) == len(graph["nodes"]) and all({e["source"], e["target"]} <= ids and e["weight"] >= 0 for e in graph["edges"])
    if intent in (I.TOP, I.TOPIC_APPLICANTS):
        if intent == I.TOPIC_APPLICANTS:
            subject_data = subject_data[subject_data.patent_id.isin(tags[tags.topic.eq(case["entity"])].patent_id)]
            subject_data = subject_data[subject_data.patent_id.isin(
                patents.loc[~patents.patent_type.str.contains("外观设计", na=False), "patent_id"])]
        expected = subject_data.groupby("applicant_std").patent_id.nunique().rename("patent_count").reset_index()
        expected = expected.sort_values(["patent_count", "applicant_std"], ascending=[False, True])
        assert [(r["applicant_std"], r["patent_count"]) for r in rows] == list(expected.head(slots["limit"]).itertuples(index=False, name=None))
    elif intent == I.INFLUENCE:
        metric = slots["metric"]
        relevant = metrics if slots.get("subject_scope") != "enterprise" else metrics[metrics.applicant_std.isin(enterprise)]
        expected = relevant.sort_values([metric, "applicant_std"], ascending=[False, True]).head(slots["limit"])
        assert [(r["applicant_std"], r[metric]) for r in rows] == list(expected[["applicant_std",metric]].itertuples(index=False, name=None))
    elif intent == I.IPC:
        frame = ipc[ipc.patent_id.isin(source)]
        if slots["ipc_scope"] == "main":
            frame = frame[frame.is_main.eq(True)]
        expected = frame.groupby("ipc_code").patent_id.nunique().rename("patent_count").reset_index()
        expected = expected.sort_values(["patent_count","ipc_code"], ascending=[False,True]).head(slots["limit"])
        assert [(r["ipc_code"],r["patent_count"]) for r in rows] == list(expected.itertuples(index=False,name=None))
    elif intent in (I.COOP, I.LAYOUT):
        expected = {b: n for a,b,n in coop[["app_a","app_b","weight"]].itertuples(index=False,name=None) if a == case["entity"]}
        expected.update({a: n for a,b,n in coop[["app_a","app_b","weight"]].itertuples(index=False,name=None) if b == case["entity"]})
        assert all(expected[r["partner"]] == r["weight"] for r in rows)
        if intent == I.LAYOUT:
            for r in rows:
                if r["topic"] is None:
                    continue
                partner_ids = set(applicants.loc[applicants.applicant_std.eq(r["partner_graph_name"]),"patent_id"])
                assert r["patent_count"] == tags.loc[tags.patent_id.isin(partner_ids) & tags.topic.eq(r["topic"]), "patent_id"].nunique()
    elif intent in (I.TREND, I.GROWTH):
        start, end = slots["start_year"], slots["end_year"]
        assert end <= 2023
        selected = yearly[yearly.year.between(start,end)]
        if intent == I.TREND:
            by_year = selected[selected.topic.eq(case["entity"])].groupby("year")["count"].sum()
            assert [r["year"] for r in rows] == list(range(start,end+1))
            assert all(r["count"] == by_year.get(r["year"],0) for r in rows)
        else:
            for r in rows:
                counts = selected[selected.topic.eq(r["topic"])].groupby("year")["count"].sum()
                assert r["patent_count"] == counts.sum() and counts[start] >= 5
                assert r["growth_rate"] == (counts.get(end,0)-counts[start])/counts[start]
            assert [r["growth_rate"] for r in rows] == sorted((r["growth_rate"] for r in rows), reverse=True)
    elif intent == I.TOPICS:
        assert graph["edges"]
        assert all(r["patent_count"] == tags.loc[tags.patent_id.isin(source) & tags.topic.eq(r["topic"]), "patent_id"].nunique() for r in rows)
    elif intent in (I.CITATION, I.DEPENDENCY):
        assert graph["edges"]
        links = cites[cites.citing_id.isin(source)].drop_duplicates(["citing_id","cited_id"])
        outside = links[links.cited_in_sample.eq(False)][["citing_id","cited_id"]]
        mapped = outside.merge(external, on=["citing_id","cited_id"])
        aliases = auxiliary.aliases()
        mapped = mapped.dropna(subset=["applicant"]).copy()
        mapped["applicant"] = mapped.applicant.map(lambda n: aliases.get(n,n))
        mapped = mapped.drop_duplicates(["citing_id","cited_id","applicant"])
        total = len(mapped[["citing_id","cited_id"]].drop_duplicates())
        external_counts = mapped.groupby("applicant").size()
        for r in rows:
            if r["citation_scope"] == "样本内":
                target = set(applicants.loc[applicants.applicant_std.eq(r["applicant_std"]),"patent_id"])
                assert r["citation_count"] == len(links[links.cited_in_sample.eq(True) & links.cited_id.isin(target)])
            else:
                assert r["citation_count"] == external_counts[r["applicant_std"]]
                if intent == I.DEPENDENCY:
                    assert r["C_A"] == total and r["dependency_exposure"] == r["citation_count"]/total
                    assert r["applicant_coverage"] == total/len(outside)
    elif intent == I.PATENTS:
        expected = patents.set_index("patent_id").title
        counts = Counter(cites[cites.cited_in_sample.eq(True)].drop_duplicates(["citing_id","cited_id"]).cited_id)
        assert all(r["patent_id"] in source and r["title"] == expected[r["patent_id"]] for r in rows)
        assert all(r["cited_count"] == counts[r["patent_id"]] for r in rows)
    assert "P1 真实样例" in result["conclusion"]


def main(output, modes):
    assert config.USE_SAMPLE and config.QA_BACKEND == "real"
    if "llm" in modes and not config.LLM_API_KEY:
        raise SystemExit("Configure LLM_API_KEY before a live model comparison")
    tables = tuple(load_table(n) for n in ("patents","applicants","patent_topic","citations","patent_ipc","cooperation"))
    tables += (auxiliary.external_applicants(),)
    assert len(tables[0]) == 481
    metrics, yearly = load_result("company_metrics"), load_result("topic_year")
    cases = CASES + [dict(id=f"B-{i:02}",question=q,error=e) for i,(q,e) in enumerate(BOUNDARIES,1)]
    records = []
    target = Path(output)
    original = llm_client.complete_json
    for mode in modes:
        for case in cases:
            calls = []
            def record(instruction, payload, **kwargs):
                event = {"stage": "classify" if "question" in payload else "organize"}
                calls.append(event)
                try:
                    response = original(instruction,payload,**kwargs)
                    event["json_ok"] = True
                    if event["stage"] == "classify":
                        event["model_intent"] = response.get("intent")
                    return response
                except llm_client.ModelUnavailable as exc:
                    event.update(json_ok=False, failure=type(exc.__cause__).__name__)
                    raise
            start = perf_counter()
            with patch.object(llm_client,"complete_json",record):
                out = answer(case["question"],mode)
            elapsed = round(perf_counter()-start,4)
            resolved = out["entities"]["resolved"]
            entity = next(iter(resolved.values()),{}).get("name")
            intent_ok = out["intent"] == case.get("intent")
            slots_ok = all(out["slots"].get(k) == v for k,v in case.get("slots",{}).items())
            scope_ok = out["slots"].get("subject_scope","all") == case.get("slots",{}).get("subject_scope","all")
            fact_ok, check = False, ""
            if out["ok"] and intent_ok:
                try:
                    check_evidence(out,case,tables,metrics,yearly)
                    fact_ok = True
                except (AssertionError, KeyError, IndexError, ValueError) as exc:
                    check = type(exc).__name__
            boundary_ok = bool(case.get("error") and not out["ok"] and case["error"] in (out["error"] or ""))
            e2e = (out["ok"] and intent_ok and slots_ok and scope_ok and fact_ok and entity == case.get("entity")) if "intent" in case else boundary_ok
            records.append(dict(case=case,requested=mode,actual=out["mode"],actual_intent=out["intent"],
                                intent_ok=intent_ok,scope_ok=scope_ok,slots_ok=slots_ok,
                                slots=out["slots"], entity=entity, candidates=out["entities"]["candidates"],
                                ok=out["ok"],fact_ok=fact_ok, fact_check_exception=check,
                                e2e=bool(e2e),error=out["error"],boundary_ok=boundary_ok,elapsed=elapsed,
                                llm_calls=calls,fallback=mode=="llm" and bool(calls) and out["mode"]=="rule",
                                rows=len(out["data"]),edges=len(out["graph"]["edges"])))
            if len(records)%12 == 0:
                print(mode, len(records), "recorded", flush=True)
            fingerprint = sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            target.write_text(json.dumps(dict(corpus_sha256=fingerprint,records=records),ensure_ascii=False,indent=2),encoding="utf-8")
    for mode in modes:
        rows = [r for r in records if r["requested"] == mode]
        print(mode,len(rows),"end-to-end passes",sum(r["e2e"] for r in rows),"mean seconds",round(mean(r["elapsed"] for r in rows),3))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["rule","llm"])
