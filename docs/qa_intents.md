# 智能问答意图与接口（P3）

依据 [团队分工](团队分工.md) 契约 F 与 [项目规划](项目规划.md) 7.4.3。本文件由 P3 补充 JSON 槽位、示例与模板对应关系。

```text
Q_TOP_APPLICANTS
Q_INFLUENTIAL_APPLICANTS
Q_COMPANY_IPC
Q_COOPERATION
Q_TOPIC_TREND
Q_GROWTH_TOPICS
Q_COMPANY_TOPICS_DOMAIN
Q_COOP_LAYOUT
Q_CITATION_APPLICANTS
Q_DEPENDENCY_EXPOSURE
Q_COMPANY_PATENTS
Q_TOPIC_APPLICANTS
```

入口：`answer(question: str, mode: str = "auto") -> dict`。返回字段为 ok、intent、slots、entities（resolved / candidates）、data、graph（nodes / edges）、conclusion、cypher、mode（llm / rule）、error、suggestions。

当前只提供返回结构，ok=false 并明确提示待实现，不返回虚构答案。P3 负责规则降级、12 个参数化只读模板与 LIMIT、实体歧义候选及 CQ10 依赖子图。大模型不直接生成 Cypher。API 配置从 core/config.py 读取。

P5 的 eval/qa_testset.csv 只读；测试集尚待 P5 出题，不能报告通过率。
