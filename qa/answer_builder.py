"""Contract F skeleton. P3 implements routing and factual answers."""


def answer(question: str, mode: str = "auto") -> dict:
    if mode not in {"auto", "rule", "llm"}:
        raise ValueError("mode must be auto, rule or llm")
    return {
        "ok": False,
        "intent": "",
        "slots": {},
        "entities": {"resolved": {}, "candidates": []},
        "data": [],
        "graph": {"nodes": [], "edges": []},
        "conclusion": "",
        "cypher": "",
        "mode": "rule",
        "error": "问答引擎待 P3 实现；当前仅提供接口骨架。",
        "suggestions": [],
    }
