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
INDUSTRY = re.compile(r"新能源汽车(?:产业|行业|领域)?")
MARKET_METRIC = r"销量|销售量|卖得[最好高多]+|营收|营业收入|市值|股价|市场份额|利润|交付量"
RANKING = r"最厉害|更厉害|最强|更强|最牛|最好|领先|领军|龙头|榜首|头名|第[一1]|头部|排名|排行|排前|前\s*[一二三四五六七八九十0-9]|最多|最高|较高|前列"
PATENT_VOLUME = r"申请量|申请数量|申请数|专利量|专利(?:总)?数|申请(?:的)?专利.{0,4}(?:多|高)|专利(?:申请)?最多|申请最多|专利.{0,4}有多少"
INFLUENCE_METRIC = r"pagerank|被引(?:用)?次数|被引(?:用)?量|被引(?:用)?.{0,6}(?:最多|最高)|度中心性|中介中心性"
RANKED_SUBJECTS = (TOP, INFLUENCE, TOPIC_APPLICANTS)
MANUFACTURER = r"(?<!汽)车企|整车(?:制造商|厂商|企业|厂)|(?:汽车|造车)(?:制造商|厂商)|汽车生产企业"
ENTERPRISE = r"企业|公司|厂商"
NETWORK_IMPACT = r"(?:引证|引用)网络.{0,20}(?:影响力|最有分量)|(?:影响力|最有分量).{0,20}(?:引证|引用)网络"
INBOUND = r"(?:常|经常|频繁).{0,6}被.{0,8}(?:引用|引证)|被.{0,8}(?:引用|引证).{0,4}(?:最多|频繁)"
RANKING_SUGGESTIONS = (
    "新能源汽车产业哪个申请主体的专利申请量最多？",
    "哪个申请主体的专利被引次数最多？",
    "按 PageRank 查看新能源汽车产业的申请主体排名。",
)
RULES = (
    (DEPENDENCY, r"依赖|暴露度|技术引用.{0,12}集中"),
    (LAYOUT, r"(合作|共同申请).{0,28}(布局|技术领域|技术主题|各自.{0,8}研究|各.*技术方向)"),
    (CITATION, r"被引用专利|引用了|引证了|引用.{0,12}(哪些|哪家|哪几家)|引用的.{0,5}(企业|主体)|被引主体|引用对象|(?:借鉴|参考).{0,10}(?:谁|哪家|哪些).{0,10}(?:技术|专利)"),
    (INFLUENCE, r"影响力|被引|pagerank|中介中心性|度中心性"),
    (GROWTH, r"(主题|技术方向).{0,20}(增长|增速)|增长.{0,12}(技术|主题)|技术.{0,20}(?:发展|升温|增长|冒头).{0,5}(?:快|猛|迅速)"),
    (TOPIC_APPLICANTS, r"(主题|技术).{0,24}(主要|领先|排名).{0,8}(主体|企业|申请人)|主要创新主体是谁|(?:谁|哪家|哪些主体).{0,8}(?:在做|主要做|在研发)|(?:哪家|哪些|谁).{0,13}(?:申请人|主体).{0,12}(?:布局|在做|在申请)"),
    (TREND, r"年度.{0,12}(申请|趋势)|逐年|每年.{0,12}(?:多少|变化)|趋势|怎么变|如何变化|申请量变化"),
    (COOP, r"合作|共同申请|(?:一起|联手|联合).{0,7}(?:搞研发|搞研究|研发|搞技术|申请|做专利)"),
    (PATENTS, r"代表性专利|专利明细|专利列表|专利记录|有哪些专利|申请了哪些专利"),
    (TOPICS, r"(涉及|布局|涵盖).{0,12}主题|主题.{0,16}(属于|领域)|(?:在|主要|重点).{0,4}(?:研究|攻关|深耕).{0,9}(?:什么|哪些)|(?:专利|研究).{0,9}(?:集中|聚焦).{0,7}(?:方向|领域|主题)"),
    (TOP, r"(申请量|申请数|专利量|专利数).{0,12}(最高|最多|较高|排名|排行|前)|排名.{0,8}申请量"),
    (IPC, r"(?<![a-z0-9])ipc(?![a-z0-9])|布局.{0,12}(技术|领域)|主要布局"),
)


class InvalidSlots(ValueError):
    """The user can correct the request."""


class UnsupportedScope(InvalidSlots):
    """A valid filter is outside the available data or metric scope."""


class IncompleteYears(InvalidSlots):
    """The requested years contain too little data for a trend."""


def rule_intent(question):
    if request_issue(question):
        return ""
    without_industry = INDUSTRY.sub("", question)
    if re.search(NETWORK_IMPACT, question) or re.search(INBOUND, question):
        return INFLUENCE
    if re.search(RANKING, question, re.I):
        if re.search(INFLUENCE_METRIC, question, re.I):
            return INFLUENCE
        if re.search(PATENT_VOLUME, question):
            if _topic_cue(without_industry):
                return TOPIC_APPLICANTS
            return TOP
    if _topic_cue(without_industry) and re.search(r"主要(?:的)?(?:申请人|创新主体|企业|公司)", question):
        return TOPIC_APPLICANTS
    for intent, pattern in RULES:
        if intent in (TOPIC_APPLICANTS, TREND) and INDUSTRY.search(question) and not _topic_cue(without_industry):
            continue
        if re.search(pattern, question, re.I):
            return intent
    return ""


def is_industry_topic(mention):
    return isinstance(mention, str) and bool(INDUSTRY.fullmatch(mention.strip()))


def _topic_cue(text):
    return bool(re.search(r"主题|这项技术|技术.{0,5}(?:方面|领域|的)|领域|方面|在.{2,28}中", text)
                or any(part.strip() for match in re.findall(QUOTED, text) for part in match))


def request_issue(question):
    """Return a clarification or scope message before any model or graph request."""
    market_request = re.sub(rf"(?:不看|不考虑|不按|不比较|而非)\s*(?:{MARKET_METRIC})", "", question)
    if re.search(MARKET_METRIC, market_request):
        return "OUT_OF_SCOPE", "当前知识图谱覆盖新能源汽车专利和引证，缺少销量、营收、市值等商业数据。可以改按专利指标比较。"
    if re.search(MANUFACTURER, question) and (re.search(RANKING, question) or re.search(INBOUND, question)):
        return "OUT_OF_SCOPE", "当前数据没有经过核验的整车制造商分类，无法限定车企排名。可查询全部申请主体，或指定一家企业查看其专利。"
    if re.search(RANKING, question) and re.search(
        r"(?:只|仅)(?:限于|限|看|查|比较|统计|筛选)?\s*(?:高校|学校|科研(?:机构|单位)|个人|政府机构|境外(?:申请人|企业))",
        question,
    ):
        return "OUT_OF_SCOPE", "当前排名支持全部申请主体或 P1 标注的企业类申请人，暂不支持这个主体类别筛选。"
    if INDUSTRY.search(question) and not _topic_cue(INDUSTRY.sub("", question)):
        if re.search(r"年度.{0,12}(?:申请|趋势)|趋势|怎么变|如何变化|申请量变化", question):
            return "NEED_CLARIFICATION", "新能源汽车是当前研究范围。查询技术主题趋势时，请指定细分主题，例如驱动电机。"
        if re.search(r"主要创新主体是谁|主要(?:企业|公司|申请人)有哪些", question) and not re.search(PATENT_VOLUME, question):
            return "NEED_CLARIFICATION", "请先选一个专利评价指标，例如专利申请量、被引次数或 PageRank。"
    without_limit = re.sub(r"前\s*(?:\d+|[一二三四五六七八九十]{1,3})(?:名|个|条)?", "", question)
    if not re.search(RANKING, without_limit, re.I):
        return ""
    if re.search(PATENT_VOLUME, question) or re.search(INFLUENCE_METRIC, question, re.I) or re.search(INBOUND, question):
        return ""
    if re.search(r"专利.{0,8}影响力|(?:引证|引用)网络|技术主题.{0,18}(?:增长|增速)", question):
        return ""
    if (_topic_cue(INDUSTRY.sub("", question))
            and re.search(r"主要(?:的)?(?:申请人|创新主体|企业|公司|主体)", question)
            and not re.search(r"最|更强|更厉害|领先|龙头|第[一1]|榜首|排名|排行", question)):
        return ""
    if INDUSTRY.search(question) or re.search(r"哪(?:家|个|些|几家)|谁|企业|公司|主体|厂商|车企|龙头", question):
        return "NEED_CLARIFICATION", "请先明确用什么指标评价企业，例如专利申请量、被引次数或 PageRank。"
    return ""


def _year_slots(question):
    explicit_years = re.findall(r"(?<!\d)(\d{4})(?=\s*年)", question)
    if any(not 1900 <= int(year) <= 2199 for year in explicit_years):
        raise UnsupportedScope("当前 P1 数据覆盖截至 2025 年，请提供 1900–2025 年范围内的年份。")
    years = [int(year) for year in re.findall(YEAR_PATTERN, question)]
    relative = re.search(r"(?:近|最近|过去)\s*(\d{1,2}|[一二三四五六七八九十])\s*年", question)
    if len(years) > 2:
        raise InvalidSlots("请提供一个年份或连续年份区间。")
    if years:
        if len(years) == 1 and (
            re.search(rf"{years[0]}\s*年?\s*(?:之前|以前|之后|以后)", question)
            or re.search(rf"(?:截至|截止至|不晚于|不早于|早于|晚于)\s*{years[0]}", question)
        ):
            raise UnsupportedScope("这类单边时间条件暂不支持，请提供明确起止年份。")
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
    if (not limit and intent in RANKED_SUBJECTS
            and re.search(r"谁|哪家|哪一家|哪个|排名第[一1]|榜首|头名", question)
            and not re.search(r"哪些|有谁|哪几", question)):
        result["limit"] = 1
    if intent in RANKED_SUBJECTS and re.search(ENTERPRISE, question):
        result["subject_scope"] = "enterprise"
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
        if re.search(NETWORK_IMPACT, question) and not re.search(r"被引(?:用)?次数|被引量", question):
            result["metric"] = "pagerank"
        for pattern, metric in (("pagerank", "pagerank"), ("中介", "betweenness"), ("度中心", "degree")):
            if re.search(pattern, question, re.I):
                result["metric"] = metric
                break
    if intent == IPC and "主分类" in question:
        result["ipc_scope"] = "main"
    slot = ENTITY_SLOT.get(intent)
    quoted = re.findall(QUOTED, question)
    if slot and (len(quoted) == 1 or quoted and re.search(r"请明确以.{1,170}作为(?:创新主体|技术主题)进行查询", question)):
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
    if intent in RANKED_SUBJECTS:
        fields["subject_scope"] = ["enterprise", "all"]
    if intent == IPC:
        fields["ipc_scope"] = ["all", "main"]
    return fields


def validate(intent, slots):
    if intent == INFLUENCE and isinstance(slots, dict) and {"start_year", "end_year"} & slots.keys():
        raise UnsupportedScope("引用影响力指标按当前数据库全时段预计算，暂不支持按年或时间区间排名。可去掉年份，或查询指定年份的专利申请量。")
    if not isinstance(intent, str) or intent not in EXAMPLES or not isinstance(slots, dict) or slots.keys() - schema(intent).keys():
        raise InvalidSlots("意图或槽位超出支持范围。")
    result = dict(slots)
    for key, bounds in (("limit", (1, 50)), ("start_year", (1900, 2100)), ("end_year", (1900, 2100))):
        if key in result and (type(result[key]) is not int or not bounds[0] <= result[key] <= bounds[1]):
            raise InvalidSlots(f"{key} 必须是 {bounds[0]}–{bounds[1]} 的整数。")
    for key, choices in (("metric", METRICS), ("ipc_scope", ("all", "main")),
                         ("subject_scope", ("all", "enterprise"))):
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
            raise UnsupportedScope("当前 P1 的数据只到 2025 年，2024–2025 年数据不完整。")
        if intent in {TREND, GROWTH} and end > 2023:
            if start > 2023:
                raise IncompleteYears("2024–2025 年数据不完整，无法用于趋势或增长分析。")
            end = 2023
        if intent == GROWTH and end <= start:
            raise InvalidSlots("增长率需要两个不同的完整年份。")
        result.update(start_year=start, end_year=end)
    return result
