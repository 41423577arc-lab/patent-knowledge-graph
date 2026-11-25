"""Verify the development baseline without a database or model credentials."""
from collections import Counter
from itertools import combinations
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import config
from core.data_loader import TABLE_COLUMNS, available_tables, load_table
from core.database import run_query
from qa.answer_builder import answer


def main():
    assert config.USE_SAMPLE, "Run baseline checks with USE_SAMPLE=true"
    assert set(available_tables()) == set(TABLE_COLUMNS)
    tables = {name: load_table(name) for name in TABLE_COLUMNS}
    patents = tables["patents"]
    assert not patents.empty
    assert patents["patent_id"].is_unique
    ids = set(patents["patent_id"])
    for name in ("applicants", "patent_ipc", "patent_topic", "patent_efficacy"):
        assert set(tables[name]["patent_id"]) <= ids, f"Dangling IDs in {name}"
    cites = tables["citations"]
    assert set(cites["citing_id"]) <= ids
    assert cites["cited_in_sample"].equals(cites["cited_id"].isin(ids))
    expected_pairs = Counter()
    for _, group in tables["applicants"].groupby("patent_id"):
        expected_pairs.update(combinations(sorted(set(group["applicant_std"])), 2))
    actual_pairs = {(r.app_a, r.app_b): r.weight for r in tables["cooperation"].itertuples()}
    assert actual_pairs == expected_pairs, "Cooperation weights differ from shared patents"
    try:
        load_table("../legacy/patents")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid table names must be rejected")

    # Explicit full-data selection must not silently load committed sample data.
    old_mode, old_dir = config.USE_SAMPLE, config.PROCESSED_DIR
    try:
        with TemporaryDirectory() as directory:
            config.USE_SAMPLE = False
            config.PROCESSED_DIR = Path(directory)
            assert available_tables() == []
            try:
                load_table("patents")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("Missing full data must fail explicitly")
            patents.to_parquet(Path(directory) / "patents.parquet", index=False)
            assert len(load_table("patents")) == len(patents)
    finally:
        config.USE_SAMPLE, config.PROCESSED_DIR = old_mode, old_dir

    result = answer("开发基线检查")
    assert set(result) == {"ok", "intent", "slots", "entities", "data", "graph",
                           "conclusion", "cypher", "mode", "error", "suggestions"}
    assert result["mode"] in {"rule", "llm"}
    # Exercise the transaction wrapper without opening a real database.
    tx = MagicMock()
    tx.run.return_value.data.return_value = [{"value": 7}]
    session = MagicMock()
    def execute_read(work):
        assert work.timeout == min(2.0, config.QUERY_TIMEOUT)
        return work(tx)
    session.execute_read.side_effect = execute_read
    with patch("core.database._driver") as driver:
        driver.return_value.session.return_value.__enter__.return_value = session
        assert run_query("RETURN $value AS value", {"value": 7}, timeout=2.0) == [{"value": 7}]
    tx.run.assert_called_once_with("RETURN $value AS value", {"value": 7})
    print("Contract checks passed:", {name: len(table) for name, table in tables.items()})


if __name__ == "__main__":
    main()
