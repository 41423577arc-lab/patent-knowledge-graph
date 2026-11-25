"""P2 -> P3 public entry point. Mock/real selection is independent of data scope."""
from core import config
from qa import answer_builder

_QUESTIONS = ["演示：创新主体申请量排名", "演示：主体 A 的代表性专利", "演示：主体 A 的依赖暴露度"]


def answer(question: str, mode: str = "auto") -> dict:
    if mode not in {"auto", "rule", "llm"}:
        raise ValueError("mode must be auto, rule or llm")
    if config.QA_BACKEND == "real":
        return answer_builder.answer(question, mode=mode)
    result = answer_builder.failure("演示桩仅支持列出的三个示例问题。")
    result["suggestions"] = list(_QUESTIONS)
    question = question.strip()
    if question not in _QUESTIONS:
        return result
    index = _QUESTIONS.index(question)
    result.update({"ok": True, "error": None, "mode": "rule"})
    if index == 0:
        result.update({"intent": "Q_TOP_APPLICANTS", "slots": {"top_n": 10},
                       "data": [{"applicant_std": "演示创新主体 A", "patent_count": 12},
                                {"applicant_std": "演示创新主体 B", "patent_count": 8}],
                       "conclusion": "【演示假数据】主体 A 为 12 件，主体 B 为 8 件，仅用于页面布局。"})
    else:
        result["entities"]["resolved"] = {"applicant": {"id": "applicant:demo-a", "name": "演示创新主体 A", "type": "Applicant"}}
        result["slots"] = {"applicant": "演示创新主体 A"}
        result["graph"] = {
            "nodes": [{"id": "applicant:demo-a", "label": "演示创新主体 A", "type": "Applicant"},
                      {"id": "patent:demo-1", "label": "演示专利 1", "type": "Patent"}],
            "edges": [{"source": "applicant:demo-a", "target": "patent:demo-1", "type": "APPLIES_FOR", "weight": 1}],
        }
        if index == 1:
            result.update({"intent": "Q_COMPANY_PATENTS", "data": [{"patent_id": "DEMO-P001", "title": "演示专利 1"}],
                           "conclusion": "【演示假数据】这里展示代表性专利和关联路径，不对应真实专利。"})
        else:
            result.update({"intent": "Q_DEPENDENCY_EXPOSURE", "data": [{"applicant_std": "演示创新主体 A", "dependency_exposure": 0.6}],
                           "conclusion": "【演示假数据】依赖暴露度 60.0%，只供 UI 演示，不代表真实业务。"})
            result["graph"]["nodes"].append({"id": "patent:demo-2", "label": "演示外部专利", "type": "Patent"})
            result["graph"]["edges"].append({"source": "patent:demo-1", "target": "patent:demo-2", "type": "CITES", "weight": 1})
    return result
