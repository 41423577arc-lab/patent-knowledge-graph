"""Neo4j read queries. Use a database account restricted to read access."""
from functools import lru_cache

from neo4j import GraphDatabase, READ_ACCESS, unit_of_work

from core import config


@lru_cache(maxsize=1)
def _driver():
    if not config.NEO4J_PASSWORD:
        raise RuntimeError("Set NEO4J_PASSWORD in .env before connecting to Neo4j")
    return GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )


def run_query(cypher: str, params: dict | None = None,
              timeout: float = 10.0) -> list[dict]:
    """Execute a trusted parameterized read query and return row dictionaries.

    READ_ACCESS is a routing hint, not a security boundary. Never pass generated
    or untrusted Cypher; use P3's reviewed templates and a read-only DB account.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    @unit_of_work(timeout=min(timeout, config.QUERY_TIMEOUT))
    def read(tx):
        return tx.run(cypher, params or {}).data()

    with _driver().session(default_access_mode=READ_ACCESS) as session:
        return session.execute_read(read)


def health_check() -> bool:
    """Return False when credentials or a reachable database are unavailable."""
    try:
        _driver().verify_connectivity()
        return True
    except Exception:
        return False
