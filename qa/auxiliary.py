"""Read P1 handoff artifacts without changing the shared data contract."""
import pandas as pd

from core import config


class DataUnavailable(RuntimeError):
    pass


def _read(name, columns, parquet=False, required=True):
    path = config.RESULTS_DIR / name
    if not path.is_file() and not required:
        return pd.DataFrame(columns=list(columns))
    try:
        frame = pd.read_parquet(path) if parquet else pd.read_csv(path, keep_default_na=False)
        return frame.loc[:, list(columns)]
    except (OSError, ValueError, KeyError, ImportError) as exc:
        raise DataUnavailable(f"P1 辅助表 {name} 缺失、不可读或字段不匹配。") from exc


def aliases():
    frame = _read("company_alias.csv", ("alias", "canonical", "method"), required=False)
    approved = frame[frame.method.isin(("manual", "auto_en"))].copy()
    approved = approved[(approved.alias != "") & (approved.canonical != "")]
    # Conflicting aliases are excluded pending review. Mappings are one hop.
    approval_counts = approved.groupby("alias").canonical.nunique()
    return dict(approved[approved.alias.isin(approval_counts[approval_counts == 1].index)][["alias", "canonical"]].values)


def merged_cooperation():
    if config.USE_SAMPLE:
        return None
    return _read("cooperation_merged.parquet", ("app_a", "app_b", "weight"), parquet=True, required=False)


def external_applicants():
    return _read("external_citation_applicants.parquet", ("citing_id", "cited_id", "applicant"), parquet=True)
