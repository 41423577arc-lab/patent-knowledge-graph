"""Short-lived in-process cache for previously verified real graph answers."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from core import config
from core.data_loader import TABLE_COLUMNS

_TTL_SECONDS = 900
_MAX_ENTRIES = 32
_lock = Lock()
_entries = OrderedDict()


def key(question):
    directory = config.DATA_DIR / "_sample" if config.USE_SAMPLE else config.PROCESSED_DIR
    results = directory / "results" if config.USE_SAMPLE else config.RESULTS_DIR
    paths = [directory / f"{name}.parquet" for name in TABLE_COLUMNS]
    paths.extend(results / name for name in ("metrics_manifest.json", "topic_year.parquet", "company_metrics.parquet"))
    paths.extend(config.RESULTS_DIR / name for name in
                 ("company_alias.csv", "cooperation_merged.parquet", "external_citation_applicants.parquet"))

    def version(path):
        try:
            info = path.stat()
            return str(path), info.st_mtime_ns, info.st_size
        except OSError:
            return str(path), None, None

    return (question, config.USE_SAMPLE, config.NEO4J_URI, config.NEO4J_USER, tuple(map(version, paths)))


def remember(cache_key, answer):
    with _lock:
        _entries[cache_key] = monotonic(), datetime.now(timezone.utc).isoformat(timespec="seconds"), deepcopy(answer)
        _entries.move_to_end(cache_key)
        while len(_entries) > _MAX_ENTRIES:
            _entries.popitem(last=False)


def recover(cache_key):
    with _lock:
        entry = _entries.get(cache_key)
        if entry is None:
            return None
        created, timestamp, answer = entry
        if monotonic() - created >= _TTL_SECONDS:
            del _entries[cache_key]
            return None
        _entries.move_to_end(cache_key)
        output = deepcopy(answer)
    output["cypher"] = ""
    output["conclusion"] = f"本次展示 {timestamp} 保存的真实查询缓存（Neo4j 暂不可用）。" + output["conclusion"]
    return output
