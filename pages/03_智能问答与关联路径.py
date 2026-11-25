"""P3: the only backend dependency is qa.service.answer()."""
import streamlit as st

from core import config
from qa.service import answer
from ui.theme import apply_theme
from ui.components import page_header, section, data_table, path_graph, error_state

apply_theme("智能问答与关联路径")
page_header("03 智能问答与关联路径", "P2 提供问答服务，P3 负责展示。")
if config.QA_BACKEND == "mock":
    st.warning("演示桩模式：以下示例为明确标注的假数据，不用于业务结论或准确率评估。")
examples = ["", "演示：创新主体申请量排名", "演示：主体 A 的代表性专利", "演示：主体 A 的依赖暴露度"]
example = st.selectbox("示例问题", examples)
question = st.text_input("请输入问题")
if st.button("查询", disabled=not (question.strip() or example)):
    result = answer(question.strip() or example)
    if result["ok"]:
        section("结论")
        st.write(result["conclusion"])
        section("数据")
        data_table(result["data"])
        section("关联路径")
        path_graph(result["graph"])
    else:
        error_state(result["error"] or "本次查询未能返回答案。")
    if result["entities"]["candidates"]:
        section("候选实体，请明确主体名称后重新提问")
        data_table(result["entities"]["candidates"])
    if result["suggestions"]:
        st.caption("可尝试：" + "；".join(result["suggestions"]))
    with st.expander("查询解释"):
        st.json({key: result[key] for key in ["intent", "slots", "entities", "mode"]})
        if result["cypher"]:
            st.code(result["cypher"], language="cypher")
