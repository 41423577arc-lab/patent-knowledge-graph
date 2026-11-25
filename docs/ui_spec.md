# UI 规范与前后端对接（P3）

P3 独占 app.py、pages/、ui/、analysis/；P2 独占 qa/。三页统一使用 ui.theme.apply_theme 与 ui.components。

| 项 | 约定 |
|---|---|
| 页面顺序 | 01 产业技术全景 → 02 创新主体与合作网络 → 03 智能问答与关联路径 |
| 标准布局 | 页头 → 筛选栏（适用时）→ 指标卡 → 图表 → 表格 / 明细 |
| 主色 / 辅色 | #2563EB / #0F766E，强调色 #D97706 |
| 术语 | 创新主体、技术主题、技术领域、依赖暴露度；不将全部申请人称为企业 |
| 计数 | 默认仅当前导入研究数据内专利，样例与全量必须标注；外部引用单独说明 |
| 数字 | Top-N 默认 10；整数千分位；百分比 1 位小数；小数指标 3 位 |
| 空 / 错 | empty_state() / error_state()，缺失值不补成零 |
| 图表 / 表格 | chart() 统一模板，data_table() 统一空状态 |

ui/components.py 提供 page_header、section、metric_row、chart、data_table、empty_state、error_state。path_graph 只用 NetworkX 做布局，方向和关系类型同时列在路径明细中。

analysis/page_data.py 只做取数、连接、筛选和简单分组，不执行 PageRank / 中心性 / 大模型。主体指标读取 load_result('company_metrics')，主题年度读取 load_result('topic_year')。

## 问答调用

页面三只导入 `from qa.service import answer`。返回结构与图字段详见 qa_intents.md。页面显示结论、数据、路径、候选实体和解释面板；当前候选以列表展示，交互式候选选择仍待 P3 完善。

QA_BACKEND=mock 时始终显示演示提示，三个示例问题结论带【演示假数据】，不能作为真实发现或评估通过率。QA_BACKEND=real 切换后页面调用方式不变，未实现 / 出错时显示真实错误，不回退假数据。

USE_SAMPLE 仅切换真实来源的开发子集与全量研究数据，和问答后端开关相互独立。当前样例没有可靠申请年 / 主题，所以年度趋势及主题年度表显示空状态；引用网络没有样例内边时 PageRank 均匀、中心性为零，不制造差异。

## 当前实现范围

已有统一页面与基础指标展示、三个问答桩示例及路径视图。完整筛选、合作网络下钻、企业详情、全部分析图表和真实问答仍由对应负责人实现，不能将当前入口检查称为完整业务验收。
