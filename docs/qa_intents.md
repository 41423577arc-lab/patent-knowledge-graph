# 智能问答意图与接口（P2）

依据 [团队分工](团队分工.md) 契约 F 与 [项目规划](项目规划.md) 7.4.3。本文件由 P2 补充 JSON 槽位、示例与模板对应关系。

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

## 唯一公开入口

`from qa.service import answer`，签名为 `answer(question: str, mode: str = "auto") -> dict`。

顶层字段固定：ok、intent、slots、entities（resolved / candidates）、data、graph（nodes / edges）、conclusion、cypher、mode（llm / rule）、error、suggestions。mode 输入允许 auto / rule / llm。问答服务由 P2 维护，页面由 P3 维护。

## 演示桩与真实实现

core/config.py 的 QA_BACKEND 独立于 USE_SAMPLE：mock 为三个固定示例的纯内存假数据，real 调用 qa.answer_builder.answer。默认 mock，不连接数据库、不调用模型；所有成功结论以【演示假数据】开头，mode=rule，cypher 为空。真实实现未完成时明确返回失败，不回退假数据。

演示问题：

- 演示：创新主体申请量排名
- 演示：主体 A 的代表性专利
- 演示：主体 A 的依赖暴露度

仅服务配置选择演示 / 真实，前端始终调用同一 answer()。真实服务中的 mode=rule 是真实数据规则查询，不等于 mock；mode=llm 也不能将假数据冒充模型结果。P2 后续完成规则降级、12 个只读模板与 LIMIT、实体消歧和 CQ10；大模型不生成自由 Cypher。

## 嵌套字段冻结

- entities.resolved：槽位名到 `{id: str, name: str, type: str}` 的映射。
- entities.candidates：`{slot: str, id: str, name: str, type: str, score: float}` 的列表；score 为 0—1。歧义时 ok=false，给出候选和澄清建议。
- graph.nodes：`{id: str, label: str, type: str}`，id 在返回图中唯一。
- graph.edges：`{source: str, target: str, type: str, weight: number}`；端点必须在 nodes 中，weight 非负。source→target 遵守 Schema 方向，共同申请逻辑无向。
- data 为该意图的行字典列表；空结果为 []，不放占位假行。无图时 nodes / edges 都是 []。
- ok=true 时 error=null；失败时有可读 error。conclusion 不含未经数据支持的断言。

P5 维护 eval/qa_testset.csv，P2 只读自测、P3 只读演示。演示桩不纳入真实问答准确率。当前测试集仍待 P5 出题。
