"""P2 real-answer orchestration, called only through qa.service."""
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
import logging
from enum import Enum
from math import isfinite
from numbers import Integral, Real

import pandas as pd

from core import config
from qa import auxiliary, cache, dependency, intents as I, llm_client
from qa.entity_linker import Catalog
from qa.retrieval import QueryUnavailable, Retrieval, ScopeMismatch

logger = logging.getLogger(__name__)


class Status(Enum):
    SUCCESS = "SUCCESS"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"
    AMBIGUOUS_ENTITY = "AMBIGUOUS_ENTITY"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    SYSTEM_ERROR = "SYSTEM_ERROR"


def _finish(result, status, requested):
    logger.info("QA response status=%s requested=%s actual=%s intent=%s",
                status.value, requested, result["mode"], result["intent"])
    return result


def _log_model_failure(stage, failure):
    cause = failure.__cause__
    status = getattr(cause, "status_code", None)
    logger.warning("QA model fallback stage=%s cause=%s http_status=%s", stage,
                   type(cause).__name__ if cause else type(failure).__name__,
                   status if type(status) is int else None)


def failure(message: str) -> dict:
    return {
        "ok": False, "intent": "", "slots": {}, "entities": {"resolved": {}, "candidates": []},
        "data": [], "graph": {"nodes": [], "edges": []}, "conclusion": "", "cypher": "",
        "mode": "rule", "error": message, "suggestions": [],
    }


def json_value(value):
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, str):
        return value
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, (Real, Decimal)):
        number = float(value)
        return number if isfinite(number) else None
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        return json_value(value.item())
    if hasattr(value, "iso_format"):  # Neo4j temporal types
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"unsupported evidence type {type(value).__name__}")


_HIGHLIGHTS = {
    I.TOP: ("applicant_std", "patent_count", "去重申请专利数"),
    I.IPC: ("ipc_code", "patent_count", "该 IPC 关联专利数"),
    I.COOP: ("partner", "weight", "共同申请专利数"),
    I.TOPICS: ("topic", "patent_count", "该主题关联专利数"),
    I.LAYOUT: ("partner", "weight", "共同申请专利数"),
    I.TOPIC_APPLICANTS: ("applicant_std", "patent_count", "该主题关联专利数"),
}


def _highlight(intent, slots, rows):
    first = rows[0]
    if intent in _HIGHLIGHTS:
        label, key, metric = _HIGHLIGHTS[intent]
        return f'返回首项为「{first[label]}」，{metric}为 {first[key]} 件。'
    if intent == I.INFLUENCE:
        metric = slots["metric"]
        label = {"cited_count": "被引次数", "pagerank": "PageRank", "degree": "度中心性", "betweenness": "中介中心性"}[metric]
        return f'返回首项为「{first["applicant_std"]}」，{label}为 {first[metric]:.6g}。'
    if intent == I.TREND:
        return f'{first["year"]} 年有 {first["count"]} 件，{rows[-1]["year"]} 年有 {rows[-1]["count"]} 件相关专利。'
    if intent == I.GROWTH:
        return f'「{first["topic"]}」在返回主题中增长率最高，为 {first["growth_rate"]:.1%}，窗口内共 {first["patent_count"]} 件。'
    if intent == I.PATENTS:
        return f'按上述标准排首位的是专利 {first["patent_id"]}，样本内被引 {first["cited_count"]} 次。'
    if intent == I.DEPENDENCY:
        assessment = ("，达到潜在单点依赖筛选条件" if first["potential_single_point"] else
                      "，未达到潜在单点依赖筛选条件" if first["single_point_assessed"] else "")
        return (f'排名首位的外部主体为「{first["applicant_std"]}」，有 {first["c_AB"]} 条去重边，'
                f'在 C_A={first["C_A"]} 的子集内暴露度为 {first["dependency_exposure"]:.1%}{assessment}；'
                f'子集共涉及 {first["involved_applicants"]} 个外部主体。')
    return (f'返回首项为「{first["applicant_std"]}」，'
            f'在{first["citation_scope"]}口径下有 {first["citation_count"]} 条去重引用边。')


def _sentences(intent, slots, retrieval, rows, requested_end):
    scope = "P1 真实样例" if config.USE_SAMPLE else "P1 全量研究数据"
    subject = f'「{retrieval.subject}」的' if retrieval.subject else ""
    start, end = slots.get("start_year"), slots.get("end_year")
    if intent == I.DEPENDENCY and rows:
        start, end = rows[0]["start_year"], rows[0]["end_year"]
    period = f"{start}—{end} 年（申请年）" if start is not None else "全部可用申请年"
    description = f"本次使用 {scope}，统计{subject}相关记录，时间范围为{period}。"
    if (requested_end and requested_end >= 2024) or (end is not None and end >= 2024):
        description += "2024–2025 年数据不完整，趋势及增长计算只使用截至 2023 年的数据。" if intent in {
            I.TREND, I.GROWTH} else "2024–2025 年的可用数据尚不完整。"
    notes = "；".join(note.rstrip("。") for note in retrieval.notes) + "。" if retrieval.notes else ""
    if rows:
        observation = _highlight(intent, slots, rows)
    elif intent == I.DEPENDENCY:
        observation = "可映射外部引证边为零，当前证据不足以计算暴露度。"
    else:
        observation = "在当前范围内未查到满足条件的记录。"
    final = dependency.PROXY_NOTE if intent == I.DEPENDENCY else (
        "结果仅覆盖当前返回记录，请结合所列口径解读。" if rows else "可尝试修改主体、主题或时间窗口。"
    )
    return [description, notes or "当前结果基于所选范围内的 P1 数据。", observation, final]


def _parse(question, try_llm):
    rule = I.rule_intent(question)
    if try_llm:
        try:
            logger.info("QA model call stage=classify")
            intent, slots = llm_client.classify(question)
            if intent and (not rule or rule == intent):
                # Rule-readable parameters and explicit candidate confirmation have precedence.
                slots = {key: value for key, value in slots.items()
                         if key not in {"subject_scope", "start_year", "end_year"}}
                logger.info("QA model accepted stage=classify intent=%s", intent)
                return intent, {**slots, **I.rule_slots(question, intent)}, True
            logger.info("QA classifier fallback reason=%s", "rule_conflict" if intent else "no_intent")
        except llm_client.ModelUnavailable as exc:
            _log_model_failure("classify", exc)
    return rule, I.rule_slots(question, rule) if rule else {}, False


def answer(question: str, mode: str = "auto") -> dict:
    if mode not in {"auto", "rule", "llm"}:
        raise ValueError("mode must be auto, rule or llm")
    result = failure("请输入一个新能源汽车专利知识图谱问题。")
    result["suggestions"] = list(I.EXAMPLES.values())
    if not isinstance(question, str) or not question.strip():
        return result
    question = question.strip()
    if len(question) > 1000:
        result["error"] = "问题最多 1000 个字符，请保留一个问题。"
        return result
    issue = I.request_issue(question)
    if issue:
        reason, message = issue
        result.update(error=message, suggestions=list(I.RANKING_SUGGESTIONS))
        return _finish(result, Status(reason), mode)
    try_llm = mode != "rule" and bool(config.LLM_API_KEY)
    if mode != "rule" and not try_llm:
        logger.info("QA classifier fallback reason=unconfigured_key")
    executed = []
    retrieval = None
    cache_key = cache.key(question)
    status = Status.NEED_CLARIFICATION
    try:
        intent, raw, model_routed = _parse(question, try_llm)
        if not intent:
            result["error"] = "目前支持 12 类新能源汽车专利问题，请参考示例。"
            return _finish(result, Status.OUT_OF_SCOPE, mode)
        result["intent"] = intent
        slots = I.validate(intent, raw)
        result["slots"] = slots
        aliases = auxiliary.aliases() if I.ENTITY_SLOT.get(intent) == "applicant" else {}
        slot = I.ENTITY_SLOT.get(intent)
        entity = None
        if slot:
            if slot == "topic" and I.is_industry_topic(slots.get(slot)):
                result.update(intent="", slots={},
                              error="新能源汽车是当前研究范围。请指定一个具体技术主题，或改按专利指标比较企业。",
                              suggestions=list(I.RANKING_SUGGESTIONS))
                return _finish(result, Status.NEED_CLARIFICATION, mode)
            catalog = Catalog(slot, aliases)
            model_mention = model_routed and slot in slots and slot not in I.rule_slots(question, intent)
            if model_mention:
                _, exact_candidates = catalog.link(question, exact_only=True)
                if exact_candidates:
                    result["entities"]["candidates"] = exact_candidates
                    slots.pop(slot)
                    result["error"] = "实体存在歧义，请确认候选后重新查询。"
                    return _finish(result, Status.AMBIGUOUS_ENTITY, mode)
            entity, candidates = catalog.link(question, slots.get(slot))
            if entity is None and model_mention:
                entity, rule_candidates = catalog.link(question)
                candidates = rule_candidates or candidates
                if entity:
                    slots.pop(slot)
                    model_routed = False
                    logger.info("QA entity fallback reason=model_entity_unresolved slot=%s", slot)
            if entity is None:
                if model_routed:
                    logger.info("QA model path ended reason=entity_unresolved slot=%s", slot)
                result["entities"]["candidates"] = candidates
                result["error"] = "实体存在歧义或只有相近名称，请确认候选后重新查询。" if candidates else (
                    "当前数据范围找不到该创新主体，请提供完整名称。" if slot == "applicant" else
                    "当前数据范围找不到该技术主题，请提供图谱中的主题全名。")
                return _finish(result, Status.AMBIGUOUS_ENTITY if candidates else Status.NEED_CLARIFICATION, mode)
            slots.setdefault(slot, entity.name)
            result["entities"]["resolved"][slot] = entity.public
        retrieval = Retrieval(intent, slots, entity, aliases, executed)
        rows = json_value(retrieval.retrieve())
        sentences = _sentences(intent, slots, retrieval, rows, raw.get("end_year"))
        result.update(data=rows, graph=json_value(retrieval.graph.public), conclusion="".join(sentences))
        if not rows:
            result["error"] = "当前数据范围不足以回答这个问题。"
            return _finish(result, Status.DATA_UNAVAILABLE, mode)
        result.update(ok=True, error=None, suggestions=[])
        status = Status.SUCCESS
        if retrieval.graph_verified and cache.key(question) == cache_key:
            cache.remember(cache_key, {**result, "cypher": "\n\n".join(executed)})
        if model_routed:
            try:
                logger.info("QA model call stage=organize")
                result.update(conclusion=llm_client.organize(sentences), mode="llm")
                logger.info("QA model accepted stage=organize")
            except llm_client.ModelUnavailable as exc:
                _log_model_failure("organize", exc)
    except QueryUnavailable as exc:
        cached = cache.recover(cache_key)
        if cached:
            return _finish(cached, Status.SUCCESS, mode)
        return _finish({**result, "error": str(exc), "cypher": "\n\n".join(executed)}, Status.SYSTEM_ERROR, mode)
    except (I.InvalidSlots, auxiliary.DataUnavailable, ScopeMismatch) as exc:
        result["error"] = str(exc)
        if isinstance(exc, I.UnsupportedScope):
            status = Status.OUT_OF_SCOPE
        elif not isinstance(exc, I.InvalidSlots) or isinstance(exc, I.IncompleteYears):
            status = Status.DATA_UNAVAILABLE
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        result["error"] = "P1 数据文件缺失、不可读或不符合契约，请核对数据和依赖配置。"
        status = Status.SYSTEM_ERROR
    finally:
        result["cypher"] = "\n\n".join(executed)
    return _finish(result, status, mode)
