"""Small, hand-verifiable checks for precomputed metrics and service boundaries."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from core import config
from core.data_loader import TABLE_COLUMNS, load_result
from qa import answer_builder
from qa.service import answer
from scripts.calculate_metrics import calculate, write_results


def fixture():
    tables = {name: pd.DataFrame(columns=columns) for name, columns in TABLE_COLUMNS.items()}
    tables["patents"] = pd.DataFrame({"patent_id": ["p1", "p2", "p3"], "is_in_sample": [True] * 3,
                                      "apply_year": [2020, 2021, 2021]})
    tables["applicants"] = pd.DataFrame({"patent_id": ["p1", "p2", "p3"], "applicant_std": ["A", "B", "C"]})
    tables["citations"] = pd.DataFrame({"citing_id": ["p1", "p1", "p2", "p1"], "cited_id": ["p2", "p2", "p3", "external"]})
    tables["patent_topic"] = pd.DataFrame({"patent_id": ["p1", "p1", "p2", "p3"],
                                          "topic": ["T", "T", "T", "X"], "domain": ["D"] * 4})
    return tables


def main():
    tables = fixture()
    results, metadata = calculate(tables)
    metrics = results["company_metrics"].set_index("applicant_std")
    assert list(metrics["patent_count"]) == [1, 1, 1]
    assert list(metrics["cited_count"]) == [0, 1, 1]
    assert list(metrics["degree"]) == [0.5, 1.0, 0.5]
    assert list(metrics["betweenness"]) == [0.0, 0.5, 0.0]
    assert metrics.loc["C", "pagerank"] > metrics.loc["B", "pagerank"] > metrics.loc["A", "pagerank"]
    assert abs(metrics["pagerank"].sum() - 1) < 1e-8
    assert metadata["edge_count"] == 2
    assert results["topic_year"].to_dict("records") == [
        {"topic": "T", "domain": "D", "year": 2020, "count": 1},
        {"topic": "T", "domain": "D", "year": 2021, "count": 1},
        {"topic": "X", "domain": "D", "year": 2021, "count": 1},
    ]
    with TemporaryDirectory() as directory:
        output = Path(directory)
        write_results(tables, output, "full")
        with patch.object(config, "USE_SAMPLE", False), patch.object(config, "RESULTS_DIR", output):
            assert len(load_result("company_metrics")) == 3
            manifest = output / "metrics_manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["scope"] = "sample"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            try:
                load_result("company_metrics")
            except ValueError:
                pass
            else:
                raise AssertionError("Cross-scope metrics must be rejected")
            data["scope"] = "full"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            result_path = output / "company_metrics.parquet"
            result_path.write_bytes(result_path.read_bytes() + b"mixed version")
            try:
                load_result("company_metrics")
            except ValueError:
                pass
            else:
                raise AssertionError("Mixed/corrupt result files must be rejected")
    with patch.object(config, "QA_BACKEND", "mock"), patch("qa.answer_builder.answer", side_effect=AssertionError("Mock called real engine")):
        for question in ["演示：创新主体申请量排名", "演示：主体 A 的代表性专利", "演示：主体 A 的依赖暴露度"]:
            result = answer(question)
            assert result["ok"] and result["error"] is None
            assert result["conclusion"].startswith("【演示假数据】")
            ids = {node["id"] for node in result["graph"]["nodes"]}
            assert all(edge["source"] in ids and edge["target"] in ids for edge in result["graph"]["edges"])
    sentinel = answer_builder.failure("real engine marker")
    with patch.object(config, "QA_BACKEND", "real"), patch("qa.answer_builder.answer", return_value=sentinel) as backend:
        assert answer("真实问题", mode="llm") is sentinel
        backend.assert_called_once_with("真实问题", mode="llm")
    print("Metric definitions, result scope, and mock/real service checks passed")


if __name__ == "__main__":
    main()
