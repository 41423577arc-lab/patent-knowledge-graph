# P3 前端最终交付说明

更新：2026-11-26。Python + Streamlit + Plotly，沿用深色青蓝设计和既有66个本地素材，没有新增运行依赖。三个业务页面及首页导航保留；正式统计不使用原型模拟数值。

## 三个页面

| 页面 | 最终功能 |
|---|---|
| 产业技术全景 | 申请年、公开国别、领域筛选；主题检索与选择；年度趋势和关联专利分页；单件详情、筛选重置、范围提示、主题标准问答入口 |
| 创新主体与合作网络 | 原始/确认别名口径切换；排行图/表选择、搜索和下拉备用；主体申请量、技术布局、年度趋势、代表性及全部专利；合作选择、共同申请证据和主体问答 |
| 智能问答与关联路径 | 三栏工作台、12类意图、跨页预填后确认发送；澄清候选、建议、编辑、重试和返回来源；实际模式、数据、图表、真实图谱节点/关系与Cypher溯源 |

跨页保存来源筛选和选择；预填、取消、编辑或重绘均不自动发送。后端仅接收用户确认的单轮问题；最近50次本地历史不作为多轮语义上下文。仅导出当前统计汇总：主题年度、主体排行、主体技术分布、合作关系，附范围说明；未经确认授权的全量原始专利及摘要不开放批量下载，仍可查看单件证据。

## P1 数据和统计口径

固定数据来源为 tianguo-P1 的 `0549afd`，57个交付文件已核验。独立快照不代表该分支全部提交已合入P3。七表通过公共加载器读取，不修改P1字段、Schema或中心性定义。

- 全量106,393件专利；Neo4j为147,174节点、571,663关系，内部引用35,114条。外部引用保留表证据，不造外部占位专利节点。
- 七表：patents、applicants、ipc、topics、efficacy、citations、cooperation。
- 辅助文件：company_alias.csv、company_patent_counts.csv、cooperation_merged.parquet、company_citation_pairs.parquet、external_citation_applicants.parquet。最后一项来自P1-4，其余来自P1-8。
- 读取company_metrics.parquet的patent_count、cited_count、pagerank、degree、betweenness，以及topic_year.parquet。网络指标保持原始标准化主体和研究内部引证网络口径，不累加别名成员中心性；共同申请网络单独展示。
- 别名委托P2 `qa.auxiliary.aliases()`，兼容相同已确认单跳映射，排除pending_review及冲突，不自行模糊扩展、不改applicant_std。页面显示展示主体包含的原始名称。
- 合并申请量按当前范围patent_id集合去重；主体详情、技术布局、专利明细使用同一集合。样例仅统计样例集合，不使用全量辅助数量或边权。
- 合作证据取双方专利集合交集去重，并校验原始合作贡献；排除自合作、未确认名称及不可靠边，不把引用当合作。保留P1原始权重溯源，不改正式表。

实际差异：现代公司合并后4,008件专利，包含四个原始名称；与Doowon Climate Control Co Ltd共同申请证据10件，P1/P2合并边累加11。另两对也存在重复贡献。P3采用去重证据数量并说明P1权重，不强求数字相等，不要求改写P2核心逻辑。

年度统计使用申请年，完整年度结论范围2010—2023；2024—2025保留明细并提示不完整。主题与领域在同一关联行匹配。预计算不支持公开国别等筛选时，使用筛选后基础表去重分组；固定网络指标明确标注范围，不冒称已筛选。

## 全量运行条件

使用已经核验的运行副本和独立Neo4j，不自动重建、导入或清空数据库。个人路径、凭据、迁移记录和验收原始证据只在本地保留。仅克隆代码不会获得本机全量数据和数据库。

```text
<基准目录>/
  source_manifest.json
  交付给同伴的内容/          # 不可变交付原件
  runtime-data/
    processed/               # 全量七表
    results/                 # 全量指标、清单、五类辅助文件
    _sample/                 # 481件样例七表
      results/               # 对应样例指标和清单
```

来源清单记录固定commit、各文件path/blob/sha256。运行副本的两份metrics_manifest保留P1 scope、source_rows及结果文件SHA-256，追加七表source_table_sha256和local_provenance.source_commit/source_directory。七表签名为加载表 `to_json(orient="split", index=False, date_format="iso", force_ascii=False)` 的UTF-8 SHA-256。source_directory指向不可变交付原件，其父目录保存source_manifest。此为本地接入证明，不冒称P1签发；迁移机器必须重新核验路径与签名，不覆盖原件。

没有有效来源证明时，指标拒绝展示，别名保守退回原始口径并提示原因，不静默显示零值。新环境需先准备上述经核验副本。

忽略的本地.env配置：DATA_DIR、USE_SAMPLE=false、QA_BACKEND=real、NEO4J_URI、NEO4J_USER、NEO4J_PASSWORD。环境变量优先。模型可选LLM_API_BASE、LLM_MODEL、LLM_API_KEY；本次实测DeepSeek / deepseek-flash。无模型密钥时规则模式仍可用。不要混用样例表和全量图；样例真实图测试需要独立匹配实例。

## P2 接口与兼容

保持 `qa.service.answer(question, mode="auto")`，支持auto/rule/llm。接入业务提交`e04cd56`，包含`68e947b`，没有改写P2代码。远端最新`aa176ad`相对此版本仅增加交付文档、README及首页说明，未自动覆盖P3首页。

跨页模板集中在ui/questions.py，以真实EXAMPLES与规则解析为准。12类为Q_TOP_APPLICANTS、Q_INFLUENTIAL_APPLICANTS、Q_COMPANY_IPC、Q_COOPERATION、Q_COOP_LAYOUT、Q_TOPIC_TREND、Q_GROWTH_TOPICS、Q_TOPIC_APPLICANTS、Q_COMPANY_TOPICS_DOMAIN、Q_CITATION_APPLICANTS、Q_DEPENDENCY_EXPOSURE、Q_COMPANY_PATENTS。

兼容读取ok、intent、slots、entities、conclusion、data、graph、cypher、mode、error、suggestions；附加状态不作为必需字段。正常、澄清、歧义、超范围、数据不足与故障分别提示。候选来自entities.candidates，建议来自suggestions，实际模型降级显示规则模式；不把所有ok=false当系统错误，不展示敏感堆栈。

| 尚不支持的请求 | 明确替代方案 |
|---|---|
| 独立专利编号意图 | 单件详情和证据；显式转查该专利申请主体的代表性专利 |
| 双主体精确合作问答 | 第二页直接查询双方共同申请专利；分别查看单主体合作问答 |
| 复合意图 | 两个独立按钮，用户分别确认，不自动连续请求 |
| 问答沿用页面公开国别等筛选 | 明确提示按后端支持范围执行，不传私有参数 |

图谱只绘真实返回并验证类型、方向和端点。视口最多128节点、200关系，合作图最多30边，明确提示裁剪；完整返回、证据及选择框保留。密集图精确点击提供表格/下拉替代。引用是技术知识关联代理，不解释为采购关系或商业风险。

## 启动与验证

使用既有requirements.txt。本次环境Python3.11.5、Streamlit1.67.0、Plotly7.2、pandas3.1.1、Neo4j5.26 / Java17；没有新增依赖或改写团队requirements。

数据库使用管理员已核验的独立实例启动脚本，确认NEO4J_HOME、NEO4J_CONF和数据位置正确且实例未重复启动。具体本机命令保存在本地迁移说明；团队文档不携带个人安装路径。不用默认端口推断实际连接，不执行reset。

在仓库根目录激活现有Python环境后启动：

```powershell
powershell -File ui/run_preview.ps1 -Python python -Port 18504
```

访问 http://127.0.0.1:18504。启动器使用官方主题参数，不覆盖共享配置；-Python可指定现有解释器。

| 验证 | 模式与结果 |
|---|---|
| python -m compileall -q ui pages analysis qa | PASS |
| python -m unittest discover -s ui/tests -p "test_*.py" -v | 全量真实环境61项通过 |
| python -m unittest discover -s qa/tests -v | 全量26项通过，1项独立样例图测试跳过 |
| python -m ui.tests.smoke | 样例/mock通过 |
| python -m eval.check_contracts | 样例/mock通过；全量另用P1校验器34项通过、8项原数据质量说明 |
| python -m eval.check_metrics | 独立三节点夹具通过，不重算正式网络指标 |
| 全量只读核查 | 57文件、七表、辅助与预计算来源、全部节点属性及关系端点/权重一致；35项环境检查通过 |
| A—F真实业务 | 产业、主体、合作、别名、边界及12类真实规则问答通过；两次有限真实模型调用通过 |
| 浏览器 | 三页在1280/1440/1920宽度通过，无横向溢出；筛选、分页、预填、取消、编辑、真实结果及返回恢复通过 |

1920宽度分页数量控件自动点击定位不稳定，使用真实键盘选择并核对页码通过，不宣称自动点击步骤通过。数据库断连、超时、缺字段、模型不可用通过隔离模拟验证，未破坏正式实例。

## 性能、阶段状态与限制

相同全量操作：冷加载约38.7→12.6秒，重复全量页13.2→1.49秒，主体页13.2→1.98秒，合作查询1.20→0.022秒，代表专利2.91→0.527秒；进程峰值约1795→998MiB。这是本机单轮服务端测量，不含浏览器绘图，存在波动。

优化为批量集合筛选、复用缓存、版本/目录/范围键、pandas3 CoW独立视图，失败指标不留缓存，低版本保留原副本策略。七表与业务结果签名一致。阶段04两项CN国别测试实际为空，不能代表真实国别性能；阶段05改用真实可选值“中国”，69,924件、2015—2023为60,079件，非空图表与导出一致。有效国别聚合单独测量约0.823秒，无有效优化前对照。

| 阶段 | 最终状态 |
|---|---|
| 00 基线 | PASS；原别名差异在01适配，模型及浏览器在后续实测 |
| 01 数据、名称、口径 | FIXED：主体去重、合作证据、原始网络指标分口径 |
| 02 问答闭环 | FIXED；不支持意图明确替代，DEGRADED |
| 03 页面功能 | FIXED；密集图点击以可靠控件替代，DEGRADED |
| 04 性能稳定性 | FIXED；结果一致，保留首次加载与视口裁剪说明 |
| 05 全量验收 | FIXED；核心流程通过，修复真实国别覆盖 |
| 06 最终交付 | 通用文档替换历史流水；个人记录及原提交本地保留，干净交付保留P2来源 |

仍有限制：P1原始缺失字段和不完整年份保留提示；未经授权明细批量下载SKIPPED。旧P5 `eval.smoke_test` 仍因独立子页入口及旧控件假设失败，原脚本未修改；ui/integration/p5-smoke-update.patch已通过apply检查，待P5审阅。独立eval/qa_testset.csv仅表头，准确率验收SKIPPED；12类工程回归不等于独立准确率。没有尚未处理的P3核心BLOCKED项。

建议维护者审核后将p3-frontend合入develop；避免重复挑选已包含的P2 `68e947b`、`e04cd56`。P1数据继续固定独立快照，升级先核对来源和统计口径，不自动替换数据库。当前不创建或合并main/develop PR。
