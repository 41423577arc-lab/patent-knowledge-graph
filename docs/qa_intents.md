# 智能问答意图与接口（P2）

依据 [团队分工](团队分工.md) 契约 F、[项目规划](项目规划.md) 7.4 和 P1 的 `docs/page_metrics.md` 第 6 节。

## 接口与模式

`from qa.service import answer`，签名为 `answer(question: str, mode: str = "auto") -> dict`。

顶层字段为 `ok`、`intent`、`slots`、`entities`、`data`、`graph`、`conclusion`、`cypher`、`mode`、`error`、`suggestions`。`entities.resolved` 为槽位到 `{id,name,type}` 的映射，候选为 `{slot,id,name,type,score}`，得分范围为 0–1。图节点为 `{id,label,type}`，边为 `{source,target,type,weight}`。图只包含可追溯的代表路径，统计范围以表格和结论为准。空图返回两个空列表。成功时 `error=null`。数据行的空值统一序列化为 JSON null。数据库溯源字段只包含本次成功执行过的 Cypher，纯表计算和缓存展示时为空。

- `QA_BACKEND=mock` 保留三个原有演示题，结论以【演示假数据】开头。
- `QA_BACKEND=real` 启用真实检索。`mode=rule` 禁用模型。配置密钥时，`auto` 与 `llm` 尝试模型分类和结论组织。接口报告实际模式 `rule` 或 `llm`。
- 空白问题、无法识别的意图和缺失必需槽位返回示例或澄清提示。主体或主题不存在时提供相似候选（能找到时）。纯规则下可用「完整名称」指定实体，P3 点击候选后生成的确认文字使用同一机制。

## 槽位

| 槽位 | 约束与默认值 |
|---|---|
| `applicant` | 主体名称，必需于 CQ03、04、07–11。1–160 字。读取标准名、原始名、P1 已确认别名。展示名映射到一个或多个原始 Applicant.name。 |
| `topic` | 主题名称，必需于 CQ05、12。1–160 字，基于当前范围的真实主题名称。 |
| `limit` | 整数 1–50，默认 10。CQ05 返回完整年度序列。 |
| `start_year`、`end_year` | 整数 1900–2100，接口校验当前 P1 交付截至 2025 年。CQ05、06 默认 2015–2023，其他意图默认选定数据集全部可用申请年。CQ02 的预计算结果按整库范围，固定时间窗暂缺。 |
| `metric` | CQ02 可选 `cited_count`（默认）、`pagerank`、`degree`、`betweenness`。 |
| `ipc_scope` | CQ03 可选 `all`（默认）或 `main`（主分类）。 |

具体年份或区间按申请年解析。“近 N 年”以最近完整年 2023 为尾年。CQ05、06 要求完整年份，对跨入 2024–2025 的请求截至 2023，并显示说明。仅请求不完整年份时返回数据不足提示。其他意图可显示 2024–2025 已收录的记录及其不完整说明。

标准名和原始名精确优先。P1 `manual`、`auto_en` 为展示层确认映射，`pending_review` 不参与合并。Kia 与 Hyundai 按 P1 别名表分开，中国南方按原实体处理。RapidFuzz 候选需要显式确认。主题保持实际名称，`（未细分）` 作为独立主题显示。

## 意图与证据

Cypher 位于 `qa/templates.py`，通过 `core.database.run_query` 绑定参数、使用统一超时和只读访问；图相关结果先比对 Neo4j 专利总数与契约表 ID（小样例核对全部 ID，全量核对 64 个分布位置）。P1 图结构与关系数量由 P1 导入器另行校验。

| 编号与意图 | 示例与表述 | 检索、字段与证据 |
|---|---|---|
| CQ01 `Q_TOP_APPLICANTS` | 专利申请量最高的创新主体有哪些？申请量前 5。 | `TOP`，按 Neo4j 原始 Applicant 节点、全部类型去重专利，行含 `applicant_std, patent_count`；逐主体排名，无图。 |
| CQ02 `Q_INFLUENTIAL_APPLICANTS` | 引用网络中哪些主体影响力高？按 PageRank 排名。 | 优先 `load_result("company_metrics")`。返回主体与 `patent_count, cited_count, pagerank, degree, betweenness`；按指定指标排序。预计算缺失时只支持用 `INFLUENCE` 计算样本内被引边数。按样本内引用网络解释，无图。 |
| CQ03 `Q_COMPANY_IPC` | 比亚迪主要布局哪些 IPC 技术领域？主分类分布。 | `IPC`，非外观设计专利按分类去重；行含 `ipc_code, patent_count, evidence`。图为 Applicant→Patent→IPC。 |
| CQ04 `Q_COOPERATION` | 某创新主体与哪些主体共同申请过专利？主要合作伙伴。 | 全量无年份条件优先 P1 `cooperation_merged`（展示层权重），图用 `COOP_EVIDENCE` 的原始关系。否则用 `COOP` 或 `COOP_WINDOW`（按共同专利去重），图取原始合作边或共同申请路径。行含 `partner, weight, cooperation_source`。 |
| CQ05 `Q_TOPIC_TREND` | 「实际主题名称」近五年的申请量如何变化？年度趋势。 | 优先 P1 `topic_year`，其次按契约专利主表与主题表计算，Neo4j 等价模板为 `TREND`。技术类去重专利按主题和申请年汇总，补零。行含 `topic, domain, year, count, topic_coverage, topic_covered_patents, technical_patents`；无图。 |
| CQ06 `Q_GROWTH_TOPICS` | 哪些技术主题增长较快？2018–2023 年增长主题。 | 沿用 CQ05 年度事实，Neo4j 对应模板为 `GROWTH`。窗口总量与首尾增长率分列，公式为 (末年量−首年量)/首年量，首年少于 5 件或未细分主题不参与筛选。行含 `topic, domain, patent_count, start_count, end_count, growth_rate` 及主题覆盖；无图。 |
| CQ07 `Q_COMPANY_TOPICS_DOMAIN` | 「实际主体名称」涉及哪些技术主题和领域？主题分别属于什么领域？ | `TOPICS` 按主题和领域统计去重技术类专利。行含 `topic, domain, patent_count, evidence`；图为 Applicant→Patent→Technology→Domain。 |
| CQ08 `Q_COOP_LAYOUT` | 「实际主体名称」的合作主体各自布局什么技术？ | 先按 CQ04 取伙伴，再用 `LAYOUT` 统计每个实际申请人节点至多三个技术主题。行含 `partner, weight, partner_graph_name, topic, domain, patent_count, patent`，缺布局时显示空值。图由合作证据和伙伴真实布局组成。 |
| CQ09 `Q_CITATION_APPLICANTS` | 「实际主体名称」引用了哪些主体的专利？被引专利涉及哪些技术领域？ | `CITATION` 统计图内去重引用边，`CITATION_LAYOUT` 取被引专利路径，`DEPENDENCY` 与外部主体明细补充外部证据。分别排序，行含 `applicant_std, citation_count, citation_scope, cited_topics, cited_ipc_codes, cited_domains`。外部被引主题、领域与 IPC 未知。 |
| CQ10 `Q_DEPENDENCY_EXPOSURE` | 「实际主体名称」的技术引用是否集中于少数外部主体？是否存在单点依赖？ | `DEPENDENCY` 分页检索主体真实专利，P1 外部引证明细按下节计算。图为 Applicant→引用专利→外部被引专利←外部主体，其中外部部分来源为 P1 辅助表。 |
| CQ11 `Q_COMPANY_PATENTS` | 「实际主体名称」有哪些代表性专利？前 5 件专利。 | `PATENTS` 对实际专利按样本内被引降序、年份降序、ID 升序排序。行含 `patent_id, title, year, patent_type, cited_count, applicants`，图为申请人与代表专利。 |
| CQ12 `Q_TOPIC_APPLICANTS` | 「实际主题名称」的主要创新主体是谁？某主题申请人排行。 | `TOPIC_APPLICANTS` 沿主题、专利、申请人路径，按指定主题和主体去重。行含 `applicant_std, patent_count, patent`，图显示代表专利和主题。 |

规则结论依次说明范围与时间、统计口径和来源、真实排名或计数，以及必要局限。缺少有效数据时返回可读信息并保留已获得的覆盖证据。图谱连接不可用时，需要图谱的意图返回失败，或展示 15 分钟内的同范围真实缓存。缓存位于 P2 进程内，最多 32 条，按源文件版本、数据库地址、用户、样例开关及问题隔离。返回结论注明缓存生成时间；切换后端进程会清空缓存。

## CQ10 的覆盖与分母

1. 按确认的主体名称集合和时间筛选所有引用方专利。
2. 用 `load_table("citations")` 取 `cited_in_sample=false` 的边，按 `(citing_id,cited_id)` 去重。与 `external_citation_applicants.parquet` 按两端专利 ID 相交。
3. 外部被引主体按确认别名归一。每个主体的 `c_AB` 为其去重外部引证边数。所有可映射主体去重后的边数是 `C_A`。输出同时给出外部总边数、映射边数、比值 `applicant_coverage`、主体总数及时间窗口。
4. `dependency_exposure=c_AB/C_A`，值为 0–1。`C_A=0` 返回数据不足；`C_A<30` 只显示数值；`C_A≥30` 且暴露度至少 0.5 时标记潜在单点依赖。多申请人可分别归属，所以各主体暴露度之和可能超过 100%。
5. 每个外部主体返回至多三条引用专利对。另按**引用方技术主题**分组，主题分母是该主题内可映射的去重引用边数。没有主题标记的边仍参与主体层指标。
6. 规划原用全引证分母，P2 采用 P1 最新可映射外部子集分母，以反映外部主体身份覆盖有限。P4 的报告和答辩应沿用这一口径与覆盖率。企业级 `company_citation_pairs` 的 `citing_patent_count` 仅为引用广度。

固定结论口径为“在可映射外部引证主体子集内，专利引用仅是技术知识关联和依赖暴露的代理指标，不代表真实商业采购依赖或供应链依赖。”

## 数据和配置

七张契约表由 `load_table` 读取；预计算由 `load_result` 验证文件校验和及 scope，P2 再核对清单和当前源表行数。P1 需为新样例和全量交付各自配套的指标及清单。QA 辅助适配只读 `core.config.RESULTS_DIR`；样例排除全量合作预聚合，外部明细必须与当前样例引证对相交。配置使用 `.env` 或环境变量，P1 数据可放到独立的 `DATA_DIR`。Neo4j 实例需与 `USE_SAMPLE` 一致。

`LLM_API_BASE=https://api.deepseek.com`、`LLM_MODEL=deepseek-flash`、`LLM_API_KEY`。模型使用现有 OpenAI SDK，JSON Output，`extra_body={"thinking":{"type":"disabled"}}`。限长、12 秒超时、无 SDK 自动重试。模型只接收原问题和意图规范，或 Python 生成的少量核验事实句。模型可组织事实句的顺序，事实、数字及限定语必须与程序输出逐字一致；出错直接使用已检索事实的规则结论。API 失败不影响规则模式。

## 验证命令

```powershell
python -m compileall -q qa
python -m unittest discover -s qa/tests -v
python -m eval.check_contracts
python -m eval.check_metrics
python -m eval.smoke_test
python -m streamlit run app.py
```

P1 的 481 件样例图启动后，可设置 `P2_LIVE_SAMPLE=1` 重跑 P2 测试，覆盖 12 类问题和 CQ10 样例事实。样例外部证据使用 P1 全量外部主体明细与当前样例引用边的交集。P3 测试应在包含问答工作台的集成工作树运行。旧 P5 冒烟脚本对“待 P2 实现”桩文本的断言应由 P5 更新。正式准确率使用 P5 完整测试集和事实标注统计，开发自测单列。
