"""Frozen seven-table contract; no silent sample/full fallback."""
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


def _table_dir():
    return config.DATA_DIR / "_sample" if config.USE_SAMPLE else config.PROCESSED_DIR


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
