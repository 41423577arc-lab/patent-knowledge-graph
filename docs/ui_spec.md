# UI 规范、v0 迁移与前端验收（P3）

更新：2026-11-25。实现保留 Python + Streamlit + Plotly；视觉来源为用户提供的 project.zip。没有将 Next.js 工程或 mock-adapter 作为正式运行服务。

## 分工与接口核查

任务文本的人员职责和 qa.answer_builder 导入示例属于旧版。当前团队分工明确：P1 管 core/scripts/data/requirements，P2 管 qa/，P3 管 app/pages/ui/analysis。本次遵循实际冻结契约 `qa.service.answer(question, mode="auto")`，不修改 qa/、core/、scripts/、data/、requirements.txt、eval/ 或其他成员文档。

优先迁移 pages/03。页面一、二保留原业务代码；通过已有 ui/theme.py、ui/components.py 获得公共视觉，不覆盖其取数和指标逻辑。新资源及适配代码均放入已有 P3 所有的 ui/，没有新增跨人共享目录。

### 已执行的迁移计划

| 范围 | 文件 | 迁移方式与依赖 |
|---|---|---|
| 原始设计素材 | ui/assets/、ui/assets.py | 逐字节复制原 public 品牌、汽车、风车公路、波纹、网络、SVG 图标；用本地 data URI 引用 |
| 全局视觉 | ui/theme.py、ui/styles.css、ui/components.py | 提取颜色/字号/间距，保留原生页面导航与组件；共用页头和 Plotly 模板 |
| 问答页面 | pages/03_智能问答与关联路径.py、ui/qa_workbench.py | 原生三栏、st.chat_input、历史、来源、图表、候选确认与大图 |
| 轻量显示适配 | ui/qa_state.py、ui/qa_visuals.py | 校验返回结构、管理会话、按返回列绘图；不做问答识别、查询或风险计算 |
| 公共框架建议 | ui/integration/streamlit-config.toml、ui/run_preview.ps1 | 官方主题配置参考及不改共享配置的预览启动器 |
| 测试交付 | ui/tests/、ui/integration/p5-smoke-update.patch | P3 自有测试和供 P5 审阅的旧冒烟检查迁移补丁 |

## 原型核查结论

直接复用：public/brand/logo_ev.svg、ev-banner.png、sidebar-energy.png、decor/ 下三种装饰及 icons/svg/ 默认/激活图标，共 66 个文件。ui/assets/manifest.json 记录 ZIP 和各资源的 SHA-256；未重新生成、裁切或替换原图。

重写：PlatformShell → 原生侧栏导航与品牌栏；QaWorkbench → Streamlit 状态与控件；ResultGraph → Plotly 原生平移、缩放、选点和弹窗；TrendChart/RankingChart → 根据真实返回字段构造 Plotly 图。

不迁移：lib/mock-adapter.ts 的问题匹配、650ms 假延迟、mock/answers.json、初始虚构答案、固定企业排名、全景数值、中心性/增长率和示例风险阈值。

源码确认的问题：

- 12 个问题入口并不等于 12 个模拟成功意图；成功 fixture 仅覆盖部分意图，其他入口会返回未支持。
- overview 的技术领域/国别主要改变选择状态；主体页的年份也未真正过滤主体数据。正式页面不能用“筛选器已选中”代替数据联动。
- 原型全景趋势按可见数据最小/最大值映射 SVG 高度，但 Y 轴仍是固定 0—100,000 刻度，数值位置不一致。正式采用 Plotly 数值坐标，不迁移原型轴刻度或最小柱宽等视觉造数。
- History 没有传给后端形成多轮上下文；正式页面同样只声明“本地历史”。
- fullscreen/clipboard 调用没有完整异常分支；正式版使用原生弹窗大图与 st.code 的复制功能。
- MIGRATION.md 的“只实现 P3”描述与 ZIP 内同时存在 overview/applicants 页面不一致，导入路径也落后于当前 service 契约。其说明仅作参考。

## 设计系统

| 项 | 从实际 CSS 提取的规则 |
|---|---|
| 背景 | #071b2a；局部径向渐变 #0b2638 |
| 导航 | #0c2538 → #0a1d2c，宽约 218px，较窄桌面约 198px |
| 面板 | #0d293d；次级 #10334a；边框 #23536c |
| 强调 | 青色 #00d9ef、蓝色 #329bf5；告警采用琥珀色，不混作业务风险评分 |
| 文字 | #f0f6fc；次级 #a8bdcc；Microsoft YaHei / Noto Sans SC / Arial 本地字体 |
| 圆角 / 阴影 | 面板 12–13px，控件 8–10px；轻量青色内发光与低透明黑影 |
| 顶栏 / 页头 | 品牌栏约 58px；独立页头约 118px；汽车与波纹绝对定位叠加，pointer-events:none |
| 数字 | 整数千分位；已知比例暴露度显示 1 位百分数；其他后端数值不猜测单位 |
| 状态 | 空结果、错误、演示与规则模式各自明确说明；缺失值不补零 |

汽车/充电桩/天际线是页头主视觉，风车/公路是侧栏主视觉，波纹和网络仅辅助叠加。装饰不占正文流、不阻挡导航和输入。所有图片和 CSS 均在本地，不依赖远程字体或图床。

CSS 使用固定的 st.container key 类与有限的语义 data-testid，不引用哈希样式类、不注入 DOM 操作脚本。原生组件与渲染层仍可能随 Streamlit 大版本变化，升级后应重跑 UI 测试。

## 问答工作台与会话

三栏比例 19 / 58 / 23；窄屏允许原生列换行，桌面保持中央优先。没有固定覆盖图谱的输入条，也没有锁死整个工作区的多层滚动。

- 左栏保存当前会话最近 50 次提交和摘要；选择历史同步恢复该条回答、数据、图谱、参数与模式。新建会话清空当前记录，不触发服务调用。
- 中栏使用单一 st.chat_input，支持中文与 Shift+Enter 换行，空输入不提交；pending/busy 和请求 ID 防止重复追加。服务失败保留完整问题，可原样重试或放回输入框编辑。
- 右栏展示当前条目的提交时数据配置、返回行数、意图、槽位、实体、后端返回的 Cypher、原始 data/graph；未提供来源、缓存标识或数据快照时明确标注，不宣称实时数据。
- QA_BACKEND=mock 的每条答案明确标注为假数据；USE_SAMPLE 与 QA_BACKEND 独立。切换历史时使用该条保存的配置，而不是用当前配置重写历史来源。
- 当前接口仅单轮问题。历史不自动传给 answer()，不宣称多轮语义理解。重启或浏览器会话结束不保证历史持久化。

候选实体仅使用返回的 entities.candidates。选择后生成可编辑的完整问题，用户明确确认才重新提交；不传私有槽位参数、不假定“示例机构”等硬编码替换规则。相似度缺失不补 100%，候选不完整时请用户补全问题。

服务异常仅展示适合用户的超时或不可用提示，不打印可能含凭据的原始异常/堆栈。失败不会回退到 v0 假数据。

## 按意图显示与图谱

ui/qa_visuals.py 覆盖规划的 12 个意图，支持正式后端常见的英文列与中文显示列。实际 data 未返回对应字段时不造图、不造数；未知列保留在数据表。

| 意图 | 展示策略 |
|---|---|
| Q_TOP_APPLICANTS / Q_TOPIC_APPLICANTS | 只对返回的主体和计数绘制排名 |
| Q_INFLUENTIAL_APPLICANTS | 允许在实际返回的被引 / PageRank / 中心性列间切换 |
| Q_COMPANY_IPC | 已返回 IPC / 领域与数值的柱状图 |
| Q_COOPERATION | 实际共同申请子图，或返回的合作次数表 / 柱状图 |
| Q_TOPIC_TREND | 明确 year / apply_year / 年份和计数才绘折线，缺年或重复序列提示核对 |
| Q_GROWTH_TOPICS | 返回规模和增长两轴时绘散点；参考线仅为当前记录中位数，不是产业阈值 |
| Q_COMPANY_TOPICS_DOMAIN / Q_COOP_LAYOUT / Q_CITATION_APPLICANTS | 优先真实返回路径；缺少图时仅表格或已有数值 |
| Q_DEPENDENCY_EXPOSURE | 已返回的 0—1 暴露度；不推算引用总数、不补阈值和风险结论 |
| Q_COMPANY_PATENTS | 返回的代表性专利列表，不用专利号或年份伪造指标 |

指标卡明确写“当前返回最高”，只从现有数值取展示最大值，不能当作数据库总体。暴露度公式是 c(A,B)/C_A；规划里的“如 30 次”未成为冻结配置，前端不自行决定样本阈值或单点依赖标记。专利引用是技术知识关联代理，不等同于采购、供应链依赖或商业风险。

图谱只使用 graph.nodes/edges：按 Schema 检查类型与方向，异常关系从绘图排除并提示，原始返回仍在溯源保留。APPLIES_FOR、CITES、HAS_IPC、INVOLVES、BELONGS_TO 有箭头；CO_APPLIED_WITH 作为无向关系，不把引用解释成合作，不补占位节点。

原生 Plotly 支持缩放/平移、节点及关系悬停/选中；详情也可用选择框访问，大图使用 st.dialog。NetworkX 只计算布局，不执行中心性或业务推断。

## P1 公共框架交付建议

当前入口 app.py 已由 P3 所有，沿用原文件的 apply_theme 调用，无需改动入口业务。P1 的 core/config/requirements 无改动；没有新增运行依赖。

ui/integration/streamlit-config.toml 是官方主题参考，由公共配置维护者审阅后复制/合并到 .streamlit/config.toml。不要覆盖已有 secrets 或个人配置。当前预览可使用 `powershell -File ui/run_preview.ps1`，通过官方 CLI 设置主题，不写共享配置。Python 可通过 -Python 参数指定，默认使用本仓库 .venv 或当前激活环境。

共用组件：apply_theme、page_header、section、metric_row、chart、data_table、empty_state、error_state 保留原签名；assets.py 统一引用已有资源。新页面调用 apply_theme 和 page_header 即可获得品牌导航和叠加页头，业务控件保持原生可交互。

## 页面一、二的设计迁移参考

本次不覆盖 pages/01、pages/02 或 analysis/page_data.py 的业务代码。

| 页面 / 原型位置 | Streamlit 推荐实现与真实数据边界 |
|---|---|
| 全景 components/overview-page.tsx：overview-filters | 年份、技术领域、国别使用原生 selectbox / multiselect，必须真正作用于同一份筛选后基础表 |
| 全景 overview-kpis / trend-layout | st.metric 与 Plotly line，使用 load_table；无可靠申请年保持空状态 |
| 全景 distribution-tabs | 原生分段选择 + IPC / patent_type / country / efficacy 实际分组；缺字段不借用原型百分比 |
| 全景 growth-panel | load_result('topic_year') 或 P1 已冻结的增长结果；当前空主题表不伪造趋势 / 增长率 |
| 全景 主体排名 | 对实际筛选专利及 applicants 连接去重，不复制 v0 企业数 |
| 主体 components/applicants-page.tsx：applicant-filters | 文本检索真实 applicant_std，筛选上下文显式展示 |
| 主体 ranking-panel / metric-tabs | load_result('company_metrics') 的 patent_count、cited_count、pagerank、degree、betweenness，前端不重算中心性 |
| 主体 network-panel | 只用 load_table('cooperation') 的真实边，NetworkX 只布局；选边后查询真实共同申请专利 |
| 主体 profile-panel / patent-query-results | 由真实主体→专利→主题/IPC 取数或冻结查询提供；没有企业简介时显示未提供 |

company_metrics 当前按整个选定研究数据范围预计算，不含年份维度。年份筛选不能把全样本 PageRank 静默标成该年指标；需要 P1 提供相应范围产物或明确标注指标仍是固定范围。原型中的规模、增长率、PageRank、地点及企业简介均不可直接迁入。

## 验证与限制

运行：

```powershell
python -m compileall -q ui pages
python -m unittest discover -s ui/tests -p "test_*.py" -v
python -m ui.tests.smoke
python -m eval.check_contracts
python -m eval.check_metrics
# 可选浏览器工具，非运行依赖：Playwright + 已安装 Edge
python -m ui.tests.browser_check --url http://127.0.0.1:18503
```

已用 Python 3.11、Streamlit 1.67.0、Plotly 7.2.0、NetworkX 3.6.1 测试。P3 自动化测试覆盖状态去重、失败保留与错误脱敏、12 意图显示、异常/空结果、原图 SHA-256、Schema 箭头、原生导航、历史恢复、新会话、候选确认。候选和部分意图使用界面测试注入的契约响应，不代表 P2 已实现真实业务。

2026-11-25 实测结果：12 项 P3 单元/组件测试全部通过，现有 eval.check_contracts 与 eval.check_metrics 通过，66 个资源哈希匹配。预览通过本机 Edge + Playwright 验收（1080px 高度）：

| 桌面宽度 | 正文可见宽 / 滚动宽 | 图片缺失 | 选点 / 关系详情 | 缩放平移 / 大图 | 新会话 | JS 错误 |
|---|---|---|---|---|---|---|
| 1280 | 1082 / 1082 | 0 | 通过 | 通过 | 通过 | 0 |
| 1440 | 1222 / 1222 | 0 | 通过 | 通过 | 通过 | 0 |
| 1920 | 1702 / 1702 | 0 | 通过 | 通过 | 通过 | 0 |

各宽度均无文档/正文横向溢出，页头保持 118px，输入框的起始位置在图谱底部之后，不遮挡图。示例按钮仅预填，必须显式发送才调用服务。浏览器截图与原始检查 JSON 输出至忽略的 tmp/visual-qa/，不混入业务数据或提交包。

P5 的旧 eval/smoke_test.py 直接运行子页面并寻找旧 text_input/查询按钮，与新原生导航和 chat_input 不兼容。本次按所有权保持 eval/ 不变，提供 ui/integration/p5-smoke-update.patch，P5 可先 git apply --check 再审阅应用；补丁转调 P3 的原生路由冒烟测试。不应将旧测试失败伪报成通过。

eval/qa_testset.csv 当前只有表头，真实问答仍待 P2；不具备意图 75% / 事实 85% 的真实业务验收条件。未执行全量 Neo4j/API 评估，不提供虚构准确率。

### 修改文件与目的

- pages/03_智能问答与关联路径.py：改为薄页面入口，保留正式服务边界。
- ui/theme.py、ui/styles.css、ui/components.py：统一设计与原生导航；保留已有组件签名。
- ui/assets.py、ui/assets/：原素材引用与校验清单。
- ui/qa_state.py：单轮会话状态、请求去重、错误与候选确认文本。
- ui/qa_visuals.py：字段适配、按意图绘图、Schema 校验、图谱布局与箭头。
- ui/qa_workbench.py：三栏页面、历史、输入、图表、溯源与大图。
- ui/run_preview.ps1、ui/integration/：主题预览与公共配置/P5 测试迁移材料。
- ui/tests/：P3 自有单元、组件与可选真实浏览器检查。
- docs/ui_spec.md：本迁移计划、设计规范、交付建议、验收与限制，避免重复报告。

## P1 数据接入更新（2026-11-25）

接入 origin/tianguo-P1 的 940c3eb，保留 P1 的数据、抽取脚本与交接文档，P3 保留公共接口及前端实现。远端分支实际名称含连字符。

实测样例：481 件专利、530 条申请人记录、1,804 条引用；前端按非外观设计得到 407 件技术类专利。三个页面均通过 AppTest 原生路由启动检查。首页新增年份/国别/领域统一筛选、技术分母说明、类型/国别/IPC/功效切换和主题表；主体页新增检索、真实申请量排名、共同申请边与网络下钻。

旧 company_metrics 的 source_rows 与新数据不符，前端拒绝复用，暂展示当前七表的真实申请量。网络中心性仍由 P1 重算交付，前端不补算。辅助别名合并结果尚未接入统一加载契约，当前明确标为未做展示层合并。问答服务仍由 P2 实现，不能把 P1 数据上传当作真实问答完成。

本地采用稀疏检出，排除大体积重复交付目录、representatives 和 raw_sample_1000；这些文件仍保留在 P1 提交与合并树中。全量 processed 表不自动复制到本机，当前验证为真实开发子集，不宣称全量/Neo4j连通验收。
