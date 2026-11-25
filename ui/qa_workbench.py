"""P3 Streamlit workbench. P2's qa.service.answer is the sole query boundary."""
from html import escape

import streamlit as st

from core import config
from ui.assets import asset_uri, heading_html, icon_html
from ui.qa_state import STATE_KEY, active_turn, clarified_question, initialize, new_conversation, process_pending, queue_question
from ui.qa_visuals import FRIENDLY, INTENTS, graph_figure, metric_cards, numeric_metrics, build_statistic, validated_graph
from ui.theme import PLOTLY_TEMPLATE, apply_theme

MOCK_EXAMPLES = ["演示：创新主体申请量排名", "演示：主体 A 的代表性专利", "演示：主体 A 的依赖暴露度"]
QUESTIONS = [
    "专利申请量最高的创新主体有哪些？", "哪些创新主体在引用网络中影响力高？",
    "某创新主体布局了哪些 IPC 技术领域？", "某创新主体与哪些主体共同申请过专利？",
    "某技术主题的年度申请量如何变化？", "哪些技术主题增长较快？",
    "某创新主体涉及哪些技术主题和领域？", "某创新主体的合作主体各自布局什么技术？",
    "某创新主体引用了哪些主体的专利？", "某创新主体的技术引用是否集中于少数外部主体？",
    "某创新主体的代表性专利有哪些？", "某技术主题的主要创新主体是谁？",
]


def _state():
    return initialize(st.session_state)


def _queue(question: str, parent_id=None):
    queue_question(_state(), question, st.session_state.get("ev_qa_mode", "auto"), config.QA_BACKEND,
                   "sample" if config.USE_SAMPLE else "full", parent_id=parent_id)


def _chat_submitted():
    _queue(st.session_state.get("ev_qa_input", ""))


def _fill_draft(text: str):
    _state()["draft"] = text
    st.session_state["ev_qa_input"] = text


def _new():
    new_conversation(_state())
    st.session_state["ev_qa_input"] = ""


def _select_history(turn_id: str):
    if not _state()["busy"]:
        _state()["active_id"] = turn_id


def _panel_heading(title: str, icon: str, note: str = ""):
    st.html(f'<div class="ev-panel-heading">{icon_html(icon)}<span>{escape(title)}</span><small>{escape(note)}</small></div>')


def _caption(text: str):
    st.html(f'<div class="ev-note">{escape(text)}</div>')


def _mode_bar():
    demo = config.QA_BACKEND == "mock"
    scope = "数据配置：开发子集" if config.USE_SAMPLE else "数据配置：全量研究数据"
    label = "问答演示桩 · 假数据" if demo else "真实问答服务入口"
    detail = "演示答案只供界面开发，不用于业务统计或准确率评估。" if demo else "结果以问答服务实际返回为准；配置不代表数据库已连接。"
    st.html(f'<div class="ev-mode-bar">{icon_html("info", size=14)}<span class="ev-pill{ " ev-pill-warm" if demo else ""}">{label}</span><span>{scope}</span><span>· {detail}</span></div>')


def _history(state: dict):
    with st.container(border=True, key="ev_qa_history"):
        _panel_heading("对话历史", "history", "当前会话")
        st.button("新建空会话", key="ev_qa_new", icon=":material/add:", width="stretch", on_click=_new, disabled=state["busy"])
        if not state["turns"]:
            st.html(f'<div class="ev-welcome"><img src="{asset_uri("icons/svg/history_default.svg")}" alt=""><p>这里将保存问题与回答摘要。<br>选择历史可恢复结果、图谱和溯源。</p></div>')
        for turn in reversed(state["turns"]):
            selected = state["active_id"] == turn["id"]
            st.button(f'{turn["time"]}  {turn["question"]}', key=f'ev_history_{turn["id"]}',
                      width="stretch", type="primary" if selected else "secondary",
                      on_click=_select_history, args=(turn["id"],), disabled=state["busy"])
            summary = turn["answer"]["conclusion"] or turn["answer"]["error"] or "暂无摘要"
            st.caption(summary[:90] + ("…" if len(summary) > 90 else ""))
        _caption("仅当前浏览器会话，保留最近 50 条；刷新或服务重启不保证保留。历史展示不等于多轮语义理解。")


def _save_view(turn_id: str, key: str):
    _state()["views"][turn_id] = st.session_state[key]


def _inspection_changed(turn_id: str, key: str):
    _state()["inspections"][turn_id] = st.session_state[key]


def _render_plot(figure, *, key: str, selectable=False):
    figure.update_layout(template=PLOTLY_TEMPLATE)
    return st.plotly_chart(figure, width="stretch", theme=None, key=key,
                           on_select="rerun" if selectable else "ignore", selection_mode="points",
                           config={"scrollZoom": True, "displaylogo": False, "toImageButtonOptions": {"format": "png"}})


@st.dialog("关联路径大图", width="large")
def _large_graph(graph: dict, turn_id: str):
    figure, notes = graph_figure(graph, height=640)
    for note in notes:
        st.warning(note)
    if figure:
        _render_plot(figure, key=f"ev_large_{turn_id}")
    _caption("箭头表示关系方向，CO_APPLIED_WITH 按无向共同申请展示。图中没有补造节点或关系。")


def _graph_view(turn: dict, state: dict):
    graph = turn["answer"]["graph"]
    figure, notes = graph_figure(graph)
    for note in notes:
        st.warning(note)
    if figure is None:
        st.info("本次回答没有可绘制的关联节点。")
        return
    if st.button("大图查看", key=f'ev_expand_{turn["id"]}', icon=":material/open_in_full:"):
        _large_graph(graph, turn["id"])
    event = _render_plot(figure, key=f'ev_graph_{turn["id"]}', selectable=True)
    points = event.get("selection", {}).get("points", []) if event else []
    event_ids = tuple(tuple(point.get("customdata", [])[:2]) for point in points)
    if event_ids and state["plot_events"].get(turn["id"]) != event_ids:
        state["plot_events"][turn["id"]] = event_ids
        state["inspections"][turn["id"]] = event_ids[-1]
        st.session_state[f'ev_inspect_{turn["id"]}'] = event_ids[-1]
    nodes, edges, _ = validated_graph(graph)
    choices = [("node", n["id"]) for n in nodes] + [("edge", str(i)) for i in range(len(edges))]
    names = {( "node", n["id"]): f'节点 · {n["label"]}（{n["type"]}）' for n in nodes}
    names.update({("edge", str(i)): f'关系 · {e["type"]} · {e["source"]} → {e["target"]}' for i, e in enumerate(edges)})
    with st.expander("实体 / 关系详情", expanded=bool(state["inspections"].get(turn["id"]))):
        options = [None, *choices]
        selected = state["inspections"].get(turn["id"])
        choice = st.selectbox("选择节点或关系", options, index=options.index(selected) if selected in options else 0,
                              format_func=lambda option: names.get(option, "点击图中节点或在此选择"),
                              key=f'ev_inspect_{turn["id"]}', on_change=_inspection_changed,
                              args=(turn["id"], f'ev_inspect_{turn["id"]}'))
        # A plot click remains authoritative when the selectbox has not been changed.
        effective = choice or selected
        if effective:
            detail = next((node for node in nodes if node["id"] == effective[1]), {}) if effective[0] == "node" else edges[int(effective[1])]
            st.json(detail, expanded=True)
    _caption("滚轮缩放，拖动平移；悬停查看类型和关系，点击后查看详情。CITES 是引用，不是合作。")


def _result_views(turn: dict, state: dict):
    answer = turn["answer"]
    options = []
    if answer["graph"]["nodes"]:
        options.append("路径图")
    if numeric_metrics(answer):
        options.append("统计图")
    if answer["data"]:
        options.append("数据表")
    if not options:
        st.info("本次查询没有返回结构化记录或关联图；页面不补造数据。")
        return
    saved = state["views"].get(turn["id"], options[0])
    key = f'ev_view_{turn["id"]}'
    view = st.radio("结果视图", options, index=options.index(saved) if saved in options else 0,
                    horizontal=True, key=key, on_change=_save_view, args=(turn["id"], key))
    if view == "路径图":
        _graph_view(turn, state)
    elif view == "统计图":
        metrics = numeric_metrics(answer)
        metric = st.selectbox("展示指标", metrics, format_func=lambda item: FRIENDLY.get(item, item), key=f'ev_metric_{turn["id"]}') if len(metrics) > 1 else metrics[0]
        figure, explanation = build_statistic(answer, metric)
        if figure is not None:
            _render_plot(figure, key=f'ev_stat_{turn["id"]}')
        else:
            st.info(explanation)
        _caption(explanation)
    else:
        st.dataframe(answer["data"], hide_index=True, width="stretch")


def _candidate_changed(turn: dict, key: str):
    index = st.session_state[key]
    candidate = turn["answer"]["entities"]["candidates"][index]
    text = clarified_question(turn, candidate)
    _state()["candidates"][turn["id"]] = {"index": index, "question": text}
    st.session_state[f'ev_clarify_{turn["id"]}'] = text


def _confirmation_edited(turn_id: str, key: str):
    _state()["candidates"][turn_id]["question"] = st.session_state[key]


def _confirm_candidate(turn_id: str, key: str):
    _queue(st.session_state.get(key, ""), parent_id=turn_id)


def _candidates(turn: dict, state: dict):
    candidates = turn["answer"]["entities"]["candidates"]
    if not candidates:
        return
    if not all(isinstance(c, dict) and isinstance(c.get("name"), str) for c in candidates):
        st.warning("候选实体格式不完整，无法安全生成确认问题。请补充完整主体名称后重新提问。")
        return
    _panel_heading("候选实体确认", "applicant")
    stored = state["candidates"].setdefault(turn["id"], {"index": 0, "question": clarified_question(turn, candidates[0])})
    key = f'ev_candidate_{turn["id"]}'
    st.selectbox("请选择需要查询的实体", range(len(candidates)), index=stored["index"],
                 format_func=lambda i: f'{candidates[i]["name"]} · {candidates[i].get("type", "类型未提供")}',
                 key=key, on_change=_candidate_changed, args=(turn, key), disabled=state["busy"])
    chosen = candidates[st.session_state[key]]
    if chosen.get("score") is not None:
        st.caption(f'后端匹配分数：{chosen["score"]}；确认后才会重新提交。')
    edit_key = f'ev_clarify_{turn["id"]}'
    if edit_key not in st.session_state:
        st.session_state[edit_key] = stored["question"]
    st.text_area("确认后的完整问题（可编辑）", key=edit_key,
                 on_change=_confirmation_edited, args=(turn["id"], edit_key), height=110, disabled=state["busy"])
    st.button("确认实体并重新查询", key=f'ev_confirm_{turn["id"]}', type="primary",
              on_click=_confirm_candidate, args=(turn["id"], edit_key), disabled=state["busy"] or not st.session_state[edit_key].strip())
    _caption("确认内容会作为新的完整问题发送给同一个 answer()；页面不创建隐藏槽位或多轮上下文。")


def _answer_panel(turn: dict, state: dict):
    answer = turn["answer"]
    title = INTENTS.get(answer["intent"], ("问答结果", "", ""))[0]
    _panel_heading("结论回答", "patent", "规则模式" if turn.get("reported_mode") == "rule" else "大模型模式" if turn.get("reported_mode") == "llm" else "未返回执行模式")
    st.html(f'<span class="ev-intent">{escape(title)} · {escape(answer["intent"] or "意图未匹配")}</span>')
    if turn["backend"] == "mock":
        st.warning("演示假数据 · 本条结果来自问答桩，不能视为实时或真实业务结论。")
    if answer["ok"]:
        st.markdown(answer["conclusion"] or "后端未提供文字结论，请查看实际返回记录。")
        if answer["intent"] == "Q_INFLUENTIAL_APPLICANTS":
            st.caption("口径：样本内引用网络指标，不代表全产业影响力；外部引用不属于图内 CITES。")
        if answer["intent"] in {"Q_COMPANY_IPC", "Q_COMPANY_TOPICS_DOMAIN", "Q_TOPIC_APPLICANTS", "Q_TOPIC_TREND", "Q_GROWTH_TOPICS"}:
            st.caption("技术类口径排除外观设计；规则抽取主题不等于标准分类，未细分主题应单列。")
        if answer["intent"] == "Q_DEPENDENCY_EXPOSURE":
            st.caption("P1 交接口径：在可映射外部主体子集内计算，需同时报告 C_A、时间窗口与覆盖。引用广度不是引用次数；C_A 不足 30 时不作单点依赖判断。页面不自行补算缺失字段。")
        cards = metric_cards(answer)
        if cards:
            for column, (label, value) in zip(st.columns(len(cards)), cards):
                column.metric(label, value)
        if answer["intent"] == "Q_DEPENDENCY_EXPOSURE":
            with st.expander("暴露度口径与局限"):
                st.caption("Exposure(A,B) = c(A,B) / C_A。仅展示服务返回值；后端未提供样本数、阈值或判断时，页面不补作风险结论。规划中的“如 30 次”不是已冻结的运行参数。")
            st.caption("专利引用是知识关联的代理指标，不等同于采购、供应链依赖或商业风险。")
        _result_views(turn, state)
    else:
        st.error(answer["error"] or "本次查询没有成功返回答案。")
        st.button("重新尝试此问题", key=f'ev_retry_{turn["id"]}', on_click=_queue,
                  args=(turn["question"], turn["id"]), disabled=state["busy"])
        st.button("放回输入框编辑", key=f'ev_edit_{turn["id"]}', on_click=_fill_draft, args=(turn["question"],), disabled=state["busy"])
    _candidates(turn, state)
    if answer["suggestions"]:
        with st.expander("后续问题建议"):
            for index, text in enumerate(answer["suggestions"]):
                st.button(text, key=f'ev_suggest_{turn["id"]}_{index}', on_click=_fill_draft, args=(text,), width="stretch", disabled=state["busy"])


def _sources(turn: dict | None, state: dict):
    with st.container(border=True, key="ev_qa_source"):
        _panel_heading("结果溯源", "citation", "只读")
        st.selectbox("回答方式", ["auto", "rule", "llm"], format_func=lambda value: {"auto": "自动选择", "rule": "规则模式", "llm": "大模型模式"}[value], key="ev_qa_mode", disabled=state["busy"])
        if turn:
            answer = turn["answer"]
            st.markdown("**数据依据**")
            st.caption("演示桩假数据" if turn["backend"] == "mock" else "后端返回结果；未提供独立数据来源或缓存标识")
            st.caption(f'提交时数据配置：{"开发子集" if turn["scope"] == "sample" else "全量研究数据"} · 请求模式 {turn["mode"]}')
            st.markdown(f'**{len(answer["data"]):,}** 行记录　·　**{len(answer["graph"]["nodes"]):,}** 节点　·　**{len(answer["graph"]["edges"]):,}** 关系')
            with st.expander("意图与槽位参数", expanded=True):
                st.caption(answer["intent"] or "未匹配意图")
                st.json(answer["slots"], expanded=True)
            with st.expander("实体链接结果"):
                st.json(answer["entities"], expanded=True)
            with st.expander("后端返回的 Cypher"):
                if answer["cypher"]:
                    st.code(answer["cypher"], language="cypher")
                else:
                    st.caption("未提供实际执行的 Cypher，页面没有构造或执行查询。")
            with st.expander("原始返回数据"):
                st.json(answer["data"], expanded=False)
            with st.expander("节点与关系明细"):
                st.json(answer["graph"], expanded=False)
            with st.expander("完整接口返回"):
                st.json(answer, expanded=False)
            _caption("结论、表格与图谱均属于当前选中记录。返回行数不等于数据库规模；配置范围不证明已连接数据库。")
        else:
            st.html(f'<div class="ev-welcome"><img src="{asset_uri("icons/svg/citation_default.svg")}" alt=""><p>等待问题与结果<br>这里将展示实际返回的字段与依据。</p></div>')
        _panel_heading("问题示例", "spark")
        if config.QA_BACKEND == "mock":
            for i, text in enumerate(MOCK_EXAMPLES):
                st.button(text, key=f"ev_example_{i}", on_click=_fill_draft, args=(text,), width="stretch", disabled=state["busy"])
            _caption("当前桩只支持上面三例；其余意图是问题模板，不能据此宣称后端已实现。")
        with st.expander("查看 12 类问题模板"):
            for (intent, (title, group, _)), question in zip(INTENTS.items(), QUESTIONS):
                st.caption(f"{group} · {title}")
                st.button(question, key=f"ev_template_{intent}", on_click=_fill_draft, args=(question,), width="stretch", disabled=state["busy"])


def render():
    apply_theme("智能问答与关联路径")
    state = _state()
    st.html(heading_html("智能问答与关联路径", "以自然语言提出完整问题，查看可解释的答案、实体关联与路径。"))
    _mode_bar()
    history, center, source = st.columns([19, 58, 23], gap="small")
    turn = active_turn(state)
    with history:
        _history(state)
    with center:
        with st.container(key="ev_qa_center"):
            question = state["pending"]["question"] if state["pending"] else turn["question"] if turn else "请输入完整问题，或从右侧选择示例开始探索"
            st.html(f'<div class="ev-question"><small>{"当前问题" if turn or state["pending"] else "智能问答工作台"}</small><p>{escape(question)}</p></div>')
            result_area = st.container(border=True, key="ev_qa_result")
            with result_area:
                if not state["pending"]:
                    if turn:
                        _answer_panel(turn, state)
                    else:
                        st.html(f'<div class="ev-welcome"><img src="{asset_uri("icons/svg/spark_active.svg")}" alt=""><h2>从一个问题开始探索</h2><p>查询技术布局、创新主体与技术引用路径。<br>每次提交一个完整问题，返回内容均有迹可循。</p></div>')
                        _caption("当前接口为单轮问答。左侧历史用于查阅，不会自动传入问答引擎作为上下文。")
            with st.container(key="ev_qa_composer"):
                submission = st.chat_input("输入完整产业技术问题…", key="ev_qa_input", max_chars=4000,
                                           disabled=state["busy"], on_submit=_chat_submitted)
                st.caption("Enter 发送 · Shift+Enter 换行 · 请使用完整问题")
            if submission and not state["pending"]:
                _queue(submission)
    with source:
        _sources(None if state["pending"] else turn, state)
    if state["pending"]:
        with result_area:
            with st.spinner("正在调用问答服务，请稍候…"):
                from qa.service import answer
                process_pending(state, answer)
        st.rerun()
