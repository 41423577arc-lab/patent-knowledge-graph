"""Validated intent routing and request parameters shared by rule and model modes."""
from datetime import date
import re

TOP, INFLUENCE, IPC, COOP, TREND, GROWTH, TOPICS, LAYOUT, CITATION, DEPENDENCY, PATENTS, TOPIC_APPLICANTS = (
    "Q_TOP_APPLICANTS", "Q_INFLUENTIAL_APPLICANTS", "Q_COMPANY_IPC", "Q_COOPERATION",
    "Q_TOPIC_TREND", "Q_GROWTH_TOPICS", "Q_COMPANY_TOPICS_DOMAIN", "Q_COOP_LAYOUT",
    "Q_CITATION_APPLICANTS", "Q_DEPENDENCY_EXPOSURE", "Q_COMPANY_PATENTS", "Q_TOPIC_APPLICANTS",
)
EXAMPLES = dict(zip(
    (TOP, INFLUENCE, IPC, COOP, TREND, GROWTH, TOPICS, LAYOUT, CITATION, DEPENDENCY, PATENTS, TOPIC_APPLICANTS),
    (
        "专利申请量最高的创新主体有哪些？", "哪些创新主体在引用网络中影响力高？",
        "某创新主体布局了哪些 IPC 技术领域？", "某创新主体与哪些主体共同申请过专利？",
        "某技术主题的年度申请量如何变化？", "哪些技术主题增长较快？",
        "某创新主体涉及哪些技术主题和领域？", "某创新主体的合作主体各自布局什么技术？",
        "某创新主体引用了哪些主体的专利？", "某创新主体的技术引用是否集中于少数外部主体？",
        "某创新主体的代表性专利有哪些？", "某技术主题的主要创新主体是谁？",
    ),
))
ENTITY_SLOT = dict.fromkeys((IPC, COOP, TOPICS, LAYOUT, CITATION, DEPENDENCY, PATENTS), "applicant")
ENTITY_SLOT.update(dict.fromkeys((TREND, TOPIC_APPLICANTS), "topic"))
METRICS = ("cited_count", "pagerank", "degree", "betweenness")
YEAR_PATTERN = r"(?<!\d)(?:19\d{2}|20\d{2}|21\d{2})(?!\d)"
QUOTED = r"「([^」]+)」|“([^”]+)”|\"([^\"]+)\""
RULES = (
    (DEPENDENCY, r"依赖|暴露度|技术引用.{0,12}集中"),
    (LAYOUT, r"(合作|共同申请).{0,28}(布局|技术领域|技术主题)"),
    (CITATION, r"被引用专利|引用了|引证了|引用.{0,12}(哪些|哪家|哪几家)|引用的.{0,5}(企业|主体)|被引主体|引用对象"),
    (INFLUENCE, r"影响力|被引|pagerank|中介中心性|度中心性"),
    (GROWTH, r"(主题|技术方向).{0,20}(增长|增速)|增长.{0,12}(技术|主题)"),
    (TOPIC_APPLICANTS, r"(主题|技术).{0,24}(主要|领先|排名).{0,8}(主体|企业|申请人)|谁.{0,12}申请最多|主要创新主体是谁"),
    (TREND, r"年度.{0,12}(申请|趋势)|趋势|怎么变|如何变化|申请量变化"),
    (COOP, r"合作|共同申请"),
    (PATENTS, r"代表性专利|专利明细|专利列表|有哪些专利"),
    (TOPICS, r"(涉及|布局|涵盖).{0,12}主题|主题.{0,16}(属于|领域)"),
    (TOP, r"(申请量|申请数|专利量|专利数).{0,12}(最高|最多|较高|排名|排行|前)|排名.{0,8}申请量"),
    (IPC, r"\bipc\b|布局.{0,12}(技术|领域)|主要布局"),
)


class InvalidSlots(ValueError):
    """The user can correct the request."""


def rule_intent(question):
    return next((intent for intent, pattern in RULES if re.search(pattern, question, re.I)), "")


def _year_slots(question):
    years = [int(year) for year in re.findall(YEAR_PATTERN, question)]
    relative = re.search(r"(?:近|最近|过去)\s*(\d{1,2}|[一二三四五六七八九十])\s*年", question)
    if len(years) > 2:
        raise InvalidSlots("请提供一个年份或连续年份区间。")
    if years:
        end = 2023 if len(years) == 1 and any(term in question for term in ("至今", "以来")) else years[-1]
        return {"start_year": years[0], "end_year": max(years[0], end) if len(years) == 1 else end}
    if relative:
        value = relative[1]
        span = int(value) if value.isdecimal() else "一二三四五六七八九十".index(value) + 1
        if not 1 <= span <= 100:
            raise InvalidSlots("相对年份须为 1–100 年。")
        return {"start_year": 2024 - span, "end_year": 2023}
    current_year = date.today().year
    for word, year in (("今年", current_year), ("去年", current_year - 1), ("前年", current_year - 2)):
        if word in question:
            return {"start_year": year, "end_year": year}
    return {}


def rule_slots(question, intent):
    result = _year_slots(question)
    limit = re.search(r"(?:\btop\s*[-－]?\s*|前\s*)(\d+|[一二三四五六七八九十]{1,3})", question, re.I)
    if limit and intent != TREND:
        value = limit[1]
        if value.isdecimal():
            result["limit"] = int(value)
        else:
            digits = "一二三四五六七八九"
            tens, separator, units = value.partition("十")
            if separator and (not tens or tens in digits and len(tens) == 1) and (not units or units in digits and len(units) == 1):
                result["limit"] = (digits.index(tens) + 1 if tens else 1) * 10 + (digits.index(units) + 1 if units else 0)
            elif len(value) == 1 and value in digits:
                result["limit"] = digits.index(value) + 1
            else:
                raise InvalidSlots("请用 1–50 表示返回数量。")
    if intent == INFLUENCE:
        for pattern, metric in (("pagerank", "pagerank"), ("中介", "betweenness"), ("度中心", "degree")):
            if re.search(pattern, question, re.I):
                result["metric"] = metric
                break
    if intent == IPC and "主分类" in question:
        result["ipc_scope"] = "main"
    slot = ENTITY_SLOT.get(intent)
    quoted = re.findall(QUOTED, question)
    if slot and quoted:
        result[slot] = next(part for part in quoted[-1] if part).strip()
    return result


def schema(intent):
    fields = {}
    if intent != TREND:
        fields["limit"] = "整数 1–50，默认 10"
    if intent != INFLUENCE:
        fields.update(start_year="整数 1900–2100", end_year="整数 1900–2100")
    if intent in ENTITY_SLOT:
        fields[ENTITY_SLOT[intent]] = "问题里原样出现的非空字符串，最多 160 字"
    if intent == INFLUENCE:
        fields["metric"] = list(METRICS)
    if intent == IPC:
        fields["ipc_scope"] = ["all", "main"]
    return fields


def validate(intent, slots):
    if not isinstance(intent, str) or intent not in EXAMPLES or not isinstance(slots, dict) or slots.keys() - schema(intent).keys():
        raise InvalidSlots("意图或槽位超出支持范围。")
    result = dict(slots)
    for key, bounds in (("limit", (1, 50)), ("start_year", (1900, 2100)), ("end_year", (1900, 2100))):
        if key in result and (type(result[key]) is not int or not bounds[0] <= result[key] <= bounds[1]):
            raise InvalidSlots(f"{key} 必须是 {bounds[0]}–{bounds[1]} 的整数。")
    for key, choices in (("metric", METRICS), ("ipc_scope", ("all", "main"))):
        if key in result and (not isinstance(result[key], str) or result[key] not in choices):
            raise InvalidSlots(f"{key} 不在支持范围。")
    slot = ENTITY_SLOT.get(intent)
    if slot in result and (not isinstance(result[slot], str) or not 0 < len(result[slot].strip()) <= 160):
        raise InvalidSlots("请提供 1–160 个字符的实体名称。")
    if intent != TREND:
        result.setdefault("limit", 10)
    if intent == IPC:
        result.setdefault("ipc_scope", "all")
    if intent == INFLUENCE:
        result.setdefault("metric", "cited_count")
    elif "start_year" in result or "end_year" in result or intent in {TREND, GROWTH}:
        start = result.get("start_year", result.get("end_year", 2015))
        end = result.get("end_year", start if "start_year" in result else 2023)
        if start > end:
            raise InvalidSlots("起始年份必须早于或等于结束年份。")
        if end > 2025:
            raise InvalidSlots("当前 P1 的数据只到 2025 年，2024–2025 年数据不完整。")
        if intent in {TREND, GROWTH} and end > 2023:
            if start > 2023:
                raise InvalidSlots("2024–2025 年数据不完整，无法用于趋势或增长分析。")
            end = 2023
        if intent == GROWTH and end <= start:
            raise InvalidSlots("增长率需要两个不同的完整年份。")
        result.update(start_year=start, end_year=end)
    return result
