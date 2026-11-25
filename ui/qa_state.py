"""P3 presentation state. History is local UI state, never implicit LLM context."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

STATE_KEY = "ev_qa"
FIELDS = {"ok", "intent", "slots", "entities", "data", "graph", "conclusion", "cypher", "mode", "error", "suggestions"}


def failure(message: str) -> dict:
    return {"ok": False, "intent": "", "slots": {}, "entities": {"resolved": {}, "candidates": []},
            "data": [], "graph": {"nodes": [], "edges": []}, "conclusion": "", "cypher": "",
            "mode": "rule", "error": message, "suggestions": []}


def normalize_answer(raw) -> dict:
    """Validate the frozen envelope; never fill missing business values with examples."""
    valid = isinstance(raw, dict) and FIELDS <= raw.keys()
    if valid:
        valid = (isinstance(raw["ok"], bool) and isinstance(raw["mode"], str) and raw["mode"] in {"llm", "rule"}
                 and all(isinstance(raw[k], str) for k in ["intent", "conclusion", "cypher"])
                 and isinstance(raw["slots"], dict) and isinstance(raw["entities"], dict)
                 and isinstance(raw["entities"].get("resolved"), dict)
                 and isinstance(raw["entities"].get("candidates"), list)
                 and isinstance(raw["data"], list) and all(isinstance(r, dict) for r in raw["data"])
                 and isinstance(raw["graph"], dict) and isinstance(raw["graph"].get("nodes"), list)
                 and isinstance(raw["graph"].get("edges"), list)
                 and isinstance(raw["suggestions"], list) and all(isinstance(s, str) for s in raw["suggestions"])
                 and (raw["error"] is None or isinstance(raw["error"], str)))
    if not valid:
        return failure("问答服务返回的结构不完整。请联系问答服务负责人核对接口；页面没有生成替代答案。")
    return deepcopy({key: raw[key] for key in FIELDS})


def initialize(session) -> dict:
    if STATE_KEY not in session:
        session[STATE_KEY] = {"turns": [], "active_id": None, "pending": None, "busy": False,
                              "draft": "", "views": {}, "candidates": {}, "inspections": {}, "plot_events": {}}
    session[STATE_KEY].setdefault("plot_events", {})
    return session[STATE_KEY]


def active_turn(state: dict) -> dict | None:
    return next((turn for turn in state["turns"] if turn["id"] == state["active_id"]), None)


def queue_question(state: dict, question: str, mode: str, backend: str, scope: str, *, parent_id=None) -> bool:
    question = question.strip()
    if not question or state["busy"] or state["pending"]:
        return False
    if mode not in {"auto", "rule", "llm"}:
        raise ValueError("Invalid request mode")
    state["draft"] = question
    state["pending"] = {"id": uuid4().hex, "question": question, "mode": mode,
                        "backend": backend, "scope": scope, "parent_id": parent_id,
                        "time": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M")}
    state["busy"] = True
    return True


def process_pending(state: dict, service) -> bool:
    request = state["pending"]
    if not request:
        return False
    try:
        if any(turn["id"] == request["id"] for turn in state["turns"]):
            return False
        reported_mode = None
        try:
            raw = service(request["question"], mode=request["mode"])
            result = normalize_answer(raw)
            if isinstance(raw, dict) and isinstance(raw.get("mode"), str) and raw["mode"] in {"llm", "rule"}:
                reported_mode = raw["mode"]
        except TimeoutError:
            result = failure("查询超时。问题已保留，请稍后重试。")
        except Exception:
            # Backend exceptions can contain credentials/URLs. Do not render their repr or traceback.
            result = failure("问答服务暂时不可用。问题已保留，请稍后重试或联系服务负责人。")
        state["turns"].append({**request, "answer": result, "reported_mode": reported_mode})
        state["turns"] = state["turns"][-50:]
        state["active_id"] = request["id"]
        state["draft"] = "" if result["ok"] else request["question"]
        return True
    finally:
        state["pending"] = None
        state["busy"] = False


def new_conversation(state: dict) -> None:
    if state["busy"]:
        return
    state.update({"turns": [], "active_id": None, "pending": None, "draft": "",
                  "views": {}, "candidates": {}, "inspections": {}, "plot_events": {}})


def clarified_question(turn: dict, candidate: dict) -> str:
    """Produce editable text for explicit confirmation, not a hidden slot override."""
    question = turn["question"]
    slot = str(candidate.get("slot", "applicant"))
    name = str(candidate.get("name", "")).strip()
    original = turn["answer"]["slots"].get(slot)
    if isinstance(original, str) and original and original in question:
        return question.replace(original, name)
    label = {"applicant": "创新主体", "company": "创新主体", "topic": "技术主题", "patent": "专利"}.get(slot, slot)
    return f"{question}\n请明确以「{name}」作为{label}进行查询。"
