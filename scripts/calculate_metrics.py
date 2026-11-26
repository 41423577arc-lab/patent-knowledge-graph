"""P1: precompute citation-network metrics and topic/year counts.

Outputs, per scope:
- data/_sample/results/{company_metrics,topic_year}.parquet + metrics_manifest.json
- data/results/{company_metrics,topic_year}.parquet + metrics_manifest.json

Run with the selected scope: USE_SAMPLE=true (sample) or false (full).
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import pandas as pd

from core import config
from core.data_loader import RESULT_COLUMNS, TABLE_COLUMNS, load_table


def calculate(tables: dict[str, pd.DataFrame]) -> tuple[dict, dict]:
    patents = tables["patents"].loc[tables["patents"]["is_in_sample"].fillna(False)]
    ids = set(patents["patent_id"])
    applicants = tables["applicants"][["patent_id", "applicant_std"]].dropna().drop_duplicates()
    applicants = applicants.loc[
        applicants["patent_id"].isin(ids) & applicants["applicant_std"].ne("")]
    owners = applicants.groupby("patent_id")["applicant_std"].agg(list).to_dict()

    graph = nx.DiGraph()
    names = sorted(set(applicants["applicant_std"]))
    graph.add_nodes_from(names)
    citations = tables["citations"][["citing_id", "cited_id"]].drop_duplicates()
    citations = citations.loc[
        citations["citing_id"].isin(ids) & citations["cited_id"].isin(ids)]
    for row in citations.itertuples(index=False):
        for source in owners.get(row.citing_id, []):
            for target in owners.get(row.cited_id, []):
                if source != target:
                    weight = graph.get_edge_data(source, target, {}).get("weight", 0) + 1
                    graph.add_edge(source, target, weight=weight)

    size = len(graph)
    pagerank = nx.pagerank(graph, alpha=0.85, weight="weight", max_iter=1000) if size else {}
    degree = (nx.degree_centrality(graph.to_undirected()) if size > 1
              else dict.fromkeys(names, 0.0))
    sample_k = min(128, size) if size > 500 else None
    betweenness = nx.betweenness_centrality(
        graph, k=sample_k, normalized=True, weight=None, seed=42
    ) if size else {}

    patent_counts = applicants.groupby("applicant_std")["patent_id"].nunique()
    cited_counts = citations.merge(applicants, left_on="cited_id", right_on="patent_id")
    cited_counts = cited_counts.drop_duplicates(["applicant_std", "citing_id", "cited_id"])
    cited_counts = cited_counts.groupby("applicant_std").size()

    metrics = pd.DataFrame([
        [name, int(patent_counts.get(name, 0)), int(cited_counts.get(name, 0)),
         pagerank.get(name, 0.0), degree.get(name, 0.0), betweenness.get(name, 0.0)]
        for name in names
    ], columns=RESULT_COLUMNS["company_metrics"])
    metrics = metrics.astype({"patent_count": "int64", "cited_count": "int64",
                              "pagerank": "float64", "degree": "float64",
                              "betweenness": "float64"})

    topics = tables["patent_topic"].dropna(subset=["topic", "domain"]).drop_duplicates()
    yearly = topics.merge(patents[["patent_id", "apply_year"]], on="patent_id")
    yearly["apply_year"] = pd.to_numeric(yearly["apply_year"], errors="coerce")
    yearly = yearly.dropna(subset=["apply_year"])
    yearly = yearly.loc[yearly["apply_year"].mod(1).eq(0)]
    yearly = (yearly.groupby(["topic", "domain", "apply_year"])["patent_id"]
              .nunique().reset_index(name="count"))
    yearly = yearly.rename(columns={"apply_year": "year"})
    yearly = yearly.astype({"year": "int64", "count": "int64"})[RESULT_COLUMNS["topic_year"]]

    return {"company_metrics": metrics, "topic_year": yearly}, {
        "node_count": size,
        "edge_count": graph.number_of_edges(),
        "betweenness": {"method": "sampled" if sample_k else "exact",
                        "k": sample_k, "seed": 42},
        "pagerank": {"alpha": 0.85,
                     "direction": "citing applicant -> cited applicant",
                     "weighted": True},
        "scope_note": "Only patents and citation endpoints in the selected dataset; no external stubs.",
    }


def write_results(tables: dict, directory: Path, scope: str) -> dict:
    if scope not in {"sample", "full"}:
        raise ValueError("scope must be sample or full")
    results, metadata = calculate(tables)
    directory.mkdir(parents=True, exist_ok=True)
    for name, table in results.items():
        table.to_parquet(directory / f"{name}.parquet", index=False)
    manifest = {
        "schema_version": 1,
        "scope": scope,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": {name: len(table) for name, table in results.items()},
        "file_sha256": {
            name: hashlib.sha256((directory / f"{name}.parquet").read_bytes()).hexdigest()
            for name in results
        },
        "source_rows": {name: len(table) for name, table in tables.items()},
        **metadata,
    }
    (directory / "metrics_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    tables = {name: load_table(name) for name in TABLE_COLUMNS}
    scope = "sample" if config.USE_SAMPLE else "full"
    target = (config.DATA_DIR / "_sample" / "results" if config.USE_SAMPLE
              else config.RESULTS_DIR)
    print(write_results(tables, target, scope))


if __name__ == "__main__":
    main()
