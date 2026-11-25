"""Shared configuration. Environment variables override the optional local .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", os.getenv("KG_NEO4J_URI", "bolt://127.0.0.1:7687"))
NEO4J_USER = os.getenv("NEO4J_USER", os.getenv("KG_NEO4J_USER", "neo4j"))
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", os.getenv("KG_NEO4J_PASSWORD", ""))
LLM_API_BASE = os.getenv("LLM_API_BASE", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT_DIR / "data"))).expanduser()
if not DATA_DIR.is_absolute():
    DATA_DIR = ROOT_DIR / DATA_DIR
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"
_sample_flag = os.getenv("USE_SAMPLE", "true").lower().strip()
if _sample_flag not in {"true", "false", "1", "0", "yes", "no"}:
    raise ValueError("USE_SAMPLE must be true or false")
USE_SAMPLE = _sample_flag in {"true", "1", "yes"}
QA_BACKEND = os.getenv("QA_BACKEND", "mock").lower().strip()
if QA_BACKEND not in {"mock", "real"}:
    raise ValueError("QA_BACKEND must be mock or real")
QUERY_TIMEOUT = float(os.getenv("QUERY_TIMEOUT", "10"))
if QUERY_TIMEOUT <= 0:
    raise ValueError("QUERY_TIMEOUT must be positive")
