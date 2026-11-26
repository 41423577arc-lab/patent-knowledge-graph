"""Presentation-only status compatibility. No new backend field is required."""
STATUSES={"SUCCESS","NEED_CLARIFICATION","AMBIGUOUS_ENTITY","OUT_OF_SCOPE","DATA_UNAVAILABLE","SYSTEM_ERROR"}
LABELS={"SUCCESS":"查询成功","NEED_CLARIFICATION":"请补充查询条件","AMBIGUOUS_ENTITY":"请选择明确的实体",
        "OUT_OF_SCOPE":"当前查询范围不支持","DATA_UNAVAILABLE":"当前范围证据不足","SYSTEM_ERROR":"服务或数据连接故障",
        "UNCLASSIFIED":"本次查询未完成"}


def response_status(answer):
    if answer["ok"]:
        return "SUCCESS" if answer["data"] or answer["graph"]["nodes"] else "DATA_UNAVAILABLE"
    explicit=answer.get("status") or answer.get("status_code")
    if isinstance(explicit,str) and explicit in STATUSES and explicit!="SUCCESS":return explicit
    if answer["entities"]["candidates"]:return "AMBIGUOUS_ENTITY"
    error=answer["error"] or ""
    if any(s in error for s in ["数据不足","数据范围不足","未查到","证据不足","数据不完整","源表行数不一致","数量或校验 ID","缺少有效","P1 辅助表","需要 P1 更新"]):return "DATA_UNAVAILABLE"
    if any(s in error for s in ["暂时不可用","当前不可用","超时","查询失败","文件缺失","缺失、不可读","结构不完整","不符合契约","配置"]):return "SYSTEM_ERROR"
    if any(s in error for s in ["暂不支持","目前支持 12","不在支持范围","超出支持","商业数据","无法限定","当前数据没有","覆盖截至","只到 2025"]):return "OUT_OF_SCOPE"
    if any(s in error for s in ["请先","请提供","请指定","请明确","请输入","找不到该","未找到实体","最多 1000","起始年份","必须是","明确起止","指定细分"]):return "NEED_CLARIFICATION"
    return "UNCLASSIFIED"
