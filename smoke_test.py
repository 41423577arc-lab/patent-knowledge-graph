# -*- coding: utf-8 -*-
from streamlit.testing.v1 import AppTest

pages = ["图谱概览", "企业技术画像", "引用关系多跳分析", "核心专利识别", "技术演进趋势", "专利检索"]
at = AppTest.from_file("app.py", default_timeout=120)
at.run()
print("page1 exception:", at.exception)
for p in pages[1:]:
    at.sidebar.radio[0].set_value(p).run()
    print(p, "exception:", at.exception, "| dataframes:", len(at.dataframe), "| charts:", len(at.get("plotly_chart")))

