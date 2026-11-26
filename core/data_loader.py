"""Frozen seven-table contract; no silent sample/full fallback."""
import hashlib
import json
from io import BytesIO

import pandas as pd

from core import config

TABLE_COLUMNS = {
    "patents": ["patent_id", "title", "abstract", "apply_date", "apply_year",
                "pub_date", "patent_type", "country", "legal_status", "is_in_sample"],
    "applicants": ["patent_id", "applicant_raw", "applicant_std", "applicant_type", "is_first"],
    "patent_ipc": ["patent_id", "ipc_code", "is_main"],
    "patent_topic": ["patent_id", "topic", "domain"],
    "patent_efficacy": ["patent_id", "efficacy_l1", "efficacy_l2", "efficacy_l3"],
    "citations": ["citing_id", "cited_id", "cited_in_sample", "cited_applicant_std"],
    "cooperation": ["app_a", "app_b", "weight"],
}

RESULT_COLUMNS = {
    "company_metrics": ["applicant_std", "patent_count", "cited_count",
                        "pagerank", "degree", "betweenness"],
    "topic_year": ["topic", "domain", "year", "count"],
}


def _table_dir():
    return config.DATA_DIR / "_sample" if config.USE_SAMPLE else config.PROCESSED_DIR


def _result_dir():
    return config.DATA_DIR / "_sample" / "results" if config.USE_SAMPLE else config.RESULTS_DIR


def available_tables() -> list[str]:
    return [name for name in TABLE_COLUMNS if (_table_dir() / f"{name}.parquet").is_file()]


def load_table(name: str) -> pd.DataFrame:
    if name not in TABLE_COLUMNS:
        raise ValueError(f"Unknown table {name!r}; choose from {list(TABLE_COLUMNS)}")
    path = _table_dir() / f"{name}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}; see docs/run.md (USE_SAMPLE={config.USE_SAMPLE})")
    table = pd.read_parquet(path)
    if list(table.columns) != TABLE_COLUMNS[name]:
        raise ValueError(f"{name} does not match contract C; see docs/schema.md")
    return table


def load_result(name: str) -> pd.DataFrame:
    """Load a precomputed result from the selected scope; never fall back."""
    if name not in RESULT_COLUMNS:
        raise ValueError(f"Unknown result {name!r}; choose from {list(RESULT_COLUMNS)}")
    scope = "sample" if config.USE_SAMPLE else "full"
    directory = _result_dir()
    path = directory / f"{name}.parquet"
    manifest_path = directory / "metrics_manifest.json"
    if not path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(
            f"Missing result/manifest at {directory}; run python -m scripts.calculate_metrics")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("scope") != scope:
        raise ValueError(f"Result scope mismatch: expected {scope}")
    content = path.read_bytes()
    if manifest.get("file_sha256", {}).get(name) != hashlib.sha256(content).hexdigest():
        raise ValueError(f"{name} checksum does not match metrics_manifest.json; regenerate results")
    table = pd.read_parquet(BytesIO(content))
    if list(table.columns) != RESULT_COLUMNS[name]:
        raise ValueError(f"{name} does not match contract C; see docs/schema.md")
    if manifest.get("row_counts", {}).get(name) != len(table):
        raise ValueError(f"{name} row count does not match metrics_manifest.json")
    table.attrs.update({"scope": scope, "metrics_manifest": manifest})
    return table
