"""P2: real-answer implementation seam, called only through qa.service."""


def answer(question: str, mode: str = "auto") -> dict:
    if mode not in {"auto", "rule", "llm"}:
        raise ValueError("mode must be auto, rule or llm")
    return failure("真实问答引擎待 P2 实现；当前不会把演示数据作为真实答案。")


def failure(message: str) -> dict:
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
        "error": message,
        "suggestions": [],
    }
