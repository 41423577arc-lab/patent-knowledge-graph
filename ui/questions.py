"""Single-intent P3 questions based on P2's delivered examples and parser."""
import re
from qa import intents as I

OPERATIONS={
    "top":(I.TOP,"专利申请量排名"), "influence":(I.INFLUENCE,"引证网络影响力"),
    "ipc":(I.IPC,"IPC 技术布局"), "cooperation":(I.COOP,"共同申请伙伴"),
    "trend":(I.TREND,"主题年度趋势"), "growth":(I.GROWTH,"技术主题增长"),
    "topics":(I.TOPICS,"技术主题与领域"), "layout":(I.LAYOUT,"合作伙伴技术布局"),
    "citation":(I.CITATION,"引用了哪些主体"), "dependency":(I.DEPENDENCY,"外部引用集中度"),
    "patents":(I.PATENTS,"代表性专利"), "topic_applicants":(I.TOPIC_APPLICANTS,"主题主要创新主体"),
}
SUBJECT_ACTIONS=("ipc","topics","patents","cooperation","layout","citation","dependency")
TOPIC_ACTIONS=("trend","topic_applicants")


class UnsupportedTemplate(ValueError):
    """A particular name/period cannot be expressed safely to the frozen parser."""


def build_question(operation, name=None, years=None):
    if operation not in OPERATIONS:raise UnsupportedTemplate("当前后端不支持该查询操作。")
    intent,_=OPERATIONS[operation]
    question=I.EXAMPLES[intent]
    slot=I.ENTITY_SLOT.get(intent)
    if slot:
        if not isinstance(name,str) or not 0<len(name.strip())<=160 or any(c in name for c in "\r\n"):
            raise UnsupportedTemplate("请先填写数据中的完整主体或技术主题名称。")
        name=name.strip()
        placeholder="某创新主体" if slot=="applicant" else "某技术主题"
        label="创新主体" if slot=="applicant" else "技术主题"
        question=question.replace(placeholder,f"{label}「{name}」")
    if years is not None:
        if len(years)!=2 or not all(type(y) is int for y in years):
            raise UnsupportedTemplate("请提供明确的起止申请年。")
        question=f"{years[0]}—{years[1]} 年，{question}"
    try:
        if I.rule_intent(question)!=intent:
            raise UnsupportedTemplate("名称中的词语与查询意图冲突，暂不能安全生成该模板；请保留证据查看或手动明确问题。")
        slots=I.rule_slots(question,intent)
        if slot and slots.get(slot)!=name:
            raise UnsupportedTemplate("名称中的引号或分隔符无法被当前后端完整识别，暂不生成该请求。")
        if years is None and {"start_year","end_year"}&slots.keys():
            raise UnsupportedTemplate("名称中的年份会被当前后端误作时间筛选，暂不生成该请求。")
        validated=I.validate(intent,slots)
        if years is not None and (validated.get("start_year"),validated.get("end_year"))!=tuple(years):
            raise UnsupportedTemplate("当前后端不能完整采用所选年份，请使用完整年度窗口或修改问题。")
    except I.InvalidSlots as exc:
        raise UnsupportedTemplate(str(exc)) from None
    return question


def subject_question(name,kind="topics"):
    if kind not in SUBJECT_ACTIONS: raise UnsupportedTemplate("未支持的主体查询操作")
    return build_question(kind,name)


def topic_question(name,kind="topic_applicants",years=None):
    if kind not in TOPIC_ACTIONS: raise UnsupportedTemplate("未支持的主题查询操作")
    return build_question(kind,name,years)


def template_entities(question):
    """Only seed local template inputs; these are not private service parameters."""
    intent=I.rule_intent(question)
    try:
        slots=I.rule_slots(question,intent) if intent else {}
    except I.InvalidSlots:
        return {}
    return {k:v for k,v in slots.items() if k in {"applicant","topic"}}


def split_compound(question):
    """Offer, never execute, the two common subject operations in a compound ask."""
    quoted=re.findall(I.QUOTED,question)
    body=re.sub(I.QUOTED,"",question)
    if len(quoted)!=1 or not re.search(r"和|以及|及|并",body):return []
    if "代表性专利" not in body or not re.search(r"技术布局|技术主题|IPC",body,re.I):return []
    name=next(p for p in quoted[0] if p)
    try:
        return [build_question("ipc" if re.search("IPC",body,re.I) else "topics",name),build_question("patents",name)]
    except UnsupportedTemplate:
        return []
