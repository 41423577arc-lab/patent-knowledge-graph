"""P3 owns this page; only answer() crosses the page/engine boundary."""
import streamlit as st

from qa.answer_builder import answer

st.title("智能问答与关联路径")
st.info("P3 开发入口：意图识别、实体链接、参数化查询与依赖路径。")
question = st.text_input("请输入问题")
if st.button("查询", disabled=not question.strip()):
    result = answer(question)
    if result["ok"]:
        st.write(result["conclusion"])
        st.dataframe(result["data"])
    else:
        st.warning(result["error"])
