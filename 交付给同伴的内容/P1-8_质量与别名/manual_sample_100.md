# P1-8 人工抽样核对（100 条）

生成时间：2026-11-25T20:09:22
文件：`manual_sample_100.csv`；随机种子 `20261125`。

## 抽样

- 从 106,393 件专利中分层抽 100 件：专利类型 → 主主题领域 → 申请年段。
- 覆盖外观设计、无 IPC、无主题、无功效、有引用、多申请人等边界情况。
- 每行给出表内预测值（`applicant_std`、`ipc_main`、`topics`、`efficacy_l1`、`cites_count`、`coop_partners`）。

## 核对方法

P5 / 人工逐条看原文，在 `label_*` 列填 `1`（正确）、`0`（错误）、`0.5`（部分正确），`notes` 写原因。建议至少两人独立核对 20 条后再统一口径。

字段对应：

| 列 | 核对对象 |
|---|---|
| `label_applicant` | 申请人拆分、去后缀、去重是否正确；对照 `applicant_raw` 与 `applicant_std` |
| `label_ipc` | 主 IPC 是否与原文一致 |
| `label_topic` | 主题是否过匹配/漏匹配；`（未细分）` 是否合理 |
| `label_efficacy` | 功效抽取是否对应原文 |
| `label_citation` | 引用方向/数量是否与原文一致；对照 `cites_count` 与 `cite_count_raw` |
| `label_cooperation` | 共同申请人配对是否正确 |

`abstract` 用于判断主题/功效；`cite_count_raw` / `cited_count_raw` 是原始字段计数，用来和表内 `cites_count` / `cited_by_count` 对照。

## 计算

对每个字段：

- 准确率 = 正确条数 / 已核对条数（`0.5` 按 0.5 计）
- 若把“表内预测”当预测集合、人工标注当参考集合，可计算 P/R/F1；关系类字段建议按边统计，不按专利统计。

## 边界

- 这是**抽样核对框**，不是已经完成的 P/R/F1；标签列留空，由 P5/人工填写。
- 100 条只能说明抽样误差，不能替代全量校验；全量结构校验见 `contract_check.json`。
