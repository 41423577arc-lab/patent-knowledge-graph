# 页面口径清单（P1 → P2/P3）

> 所有图/表的标题都要能回答三个问题：**分母是谁、时间窗口是什么、数据覆盖多少**。
> 数据入口：`core.data_loader.load_table()`（七表）、`core.database.run_query()`（Neo4j）、`data/results/*.parquet|csv`（辅助表）。

## 1. 三个总分母

| 口径 | 数值 | 用在哪 |
|---|---:|---|
| 全部专利 | **106,393** | 专利总量、类型分布、国别分布、企业专利数、专利明细 |
| 技术类专利（非外观设计） | **86,814** | IPC、主题、功效、技术布局、技术趋势 |
| 有主题的专利 | **71,487**（82.35%） | 主题趋势、主题排名；页面标覆盖率 |
| 有 IPC 的专利 | **85,946**（99.0%） | IPC 分布；页面标 868 件无 IPC |
| 有功效的专利 | **77,617**（89.41%） | 功效分布；页面标缺失 |

**规则**：技术类和全部专利不能混用。企业“专利数”用 106,393 口径；企业“技术布局”用 86,814 口径。图标题写“占全部专利”或“占技术类专利”。

## 2. 时间窗口

- 趋势分析用 **2010/2015—2023**；2024—2025 标“不完整”，不进入趋势结论。
- 清洗后申请量：2024 年 **6,519**、2025 年 **236**；公开量：2024 年 **13,938**、2025 年 **6,976**。
- 2025 年数据来自 2025-08 导出，不是全年；不要写“2024—2025 下降/爆发”。
- 申请年范围 1962—2025，公开年 1969—2025；早期年份样本很少，趋势图建议从 2010 或 2015 开始。

## 3. 页面一：产业技术全景

| 图表 | 数据源 | 分母 / 过滤 | 标题必须写 |
|---|---|---|---|
| 指标卡：专利总量 | `patents` | 106,393 | 全部专利 |
| 指标卡：创新主体 | `applicants` 或 `company_patent_counts` | 27,557 原始 / 27,190 合并后 | 写清是否展示层合并 |
| 指标卡：主题数 | `patent_topic` | 50 个主题、8 个领域 | 主题覆盖率 82.35% |
| 年度申请趋势 | `patents.apply_year` | 2010/2015—2023 | 2024—2025 不完整，已截断 |
| 专利类型分布 | `patents.patent_type` | 106,393 | 全部专利 |
| 公开国别分布 | `patents.country` | 106,393 | 公开国别，不是申请人国别 |
| IPC 分布 | `patent_ipc` | 85,946 有 IPC / 86,814 技术类 | 技术类专利；868 件无 IPC |
| 功效分布 | `patent_efficacy` | 77,617 有功效 / 86,814 | 技术类专利；89.41% 覆盖 |
| 创新主体排名 | `company_patent_counts.csv` | 合并后 canonical | 展示层合并；契约表未改 |
| 主题年度表 | `load_result("topic_year")` | 样例 295 行 / 全量 1,293 行；71,487 有主题 | 2010/2015—2023；`（未细分）` 单列，不混入细粒度主题 |

## 4. 页面二：创新主体与合作网络

| 图表 | 数据源 | 口径 / 注意 |
|---|---|---|
| 企业专利申请量排行 | `company_patent_counts.csv` | `patent_count` 是去重专利数；同一专利多申请人会在多个企业各计一次 |
| 企业被引排名 | `load_result("company_metrics")` 的 `cited_count` | 只含样本内 CITES；标题写“样本内引用网络” |
| PageRank / 度中心性 / 中介中心性 | `load_result("company_metrics")` | 预计算，前端不重算；只能称“样本内引用网络指标” |
| 企业技术布局 | Neo4j `HAS_IPC` / `INVOLVES` | 技术类口径；外观设计没有技术属性 |
| 企业合作网络 | `cooperation_merged.parquet` | 9,750 条边；展示层合并；`weight` 是共同专利数 |
| 企业详情 / 关联专利 | `patents` + `applicants` | 全部专利口径；外观设计也包含 |
| 申请人类型 | `applicants.applicant_type` | 空值显示“未知”（2,931 行）；“境外/未知”保持原样 |

**合作网络必须标**：展示层合并（393 条别名），Kia 与 Hyundai 不合并，`中国南方` 是 `pending_review`，`中国南方 ↔ 重庆长安` 不能当作已确认关系。

## 5. 页面三：智能问答与关联路径

| 意图 | 推荐数据源 | 必须标注 |
|---|---|---|
| `Q_TOP_APPLICANTS` | `company_patent_counts.csv` 或 Neo4j Applicant | 是否展示层合并；专利数口径 106,393 |
| `Q_INFLUENTIAL_APPLICANTS` | `load_result("company_metrics")` 或 Neo4j `CITES` | 样本内引用网络；CITES 35,114 条；P2 用预计算，P3 图查询同一口径 |
| `Q_COMPANY_IPC` | Neo4j `HAS_IPC` | 技术类口径；主/副 IPC 说明 |
| `Q_COOPERATION` | `cooperation_merged.parquet` | 展示层；Kia/Hyundai 分开；中国南方待核 |
| `Q_TOPIC_TREND` | `load_result("topic_year")` | 2010/2015—2023；2024—2025 不完整；主题覆盖 82.35% |
| `Q_GROWTH_TOPICS` | `load_result("topic_year")` | 低基数主题的增长率可能失真；标样本量 |
| `Q_COMPANY_TOPICS_DOMAIN` | Neo4j 3 跳 `APPLIES_FOR→INVOLVES→BELONGS_TO` | 技术类口径；外观设计无主题 |
| `Q_COOP_LAYOUT` | `cooperation_merged` + 技术布局 | 展示层合作 + 技术类口径 |
| `Q_CITATION_APPLICANTS` | Neo4j `CITES` + `external_citation_applicants.parquet` | 样本内/外分开；外部主体覆盖 3.9% |
| `Q_DEPENDENCY_EXPOSURE` | `external_citation_applicants.parquet` + `applicants.parquet` + `company_alias.csv` | 见下一节；标 C_A 与覆盖 |
| `Q_COMPANY_PATENTS` | Neo4j Patent / `patents` | 全部专利；可分类型 |
| `Q_TOPIC_APPLICANTS` | `patent_topic` + `applicants` | 技术类口径；`（未细分）` 单列 |

## 6. CQ10 技术依赖暴露度怎么算

推荐用 `external_citation_applicants.parquet` 的明细，不要只用 `company_citation_pairs.parquet` 的 `citing_patent_count`。

1. 企业 A 的引用专利集合：`applicants.parquet` 中 `applicant_std` 经 `company_alias.csv` 归一到 A 的 `patent_id`。
2. 对 A 的每件引用专利，取 `external_citation_applicants` 中 `citing_id = patent_id` 的行。
3. 外部主体 B 的引用边数 `c(A,B)` = 该企业集合下 `(citing_id, cited_id)` 去重后、`cited_id` 的申请人为 B 的边数。
4. 分母 `C_A` = A 的样本内专利在**可映射主体子集**内的外部引用边数（`(citing_id, cited_id)` 去重）。全量外部边 407,803，其中只有 15,908 条有主体明细（3.90%），所以 `C_A` 不是全量外部引用数。
5. `Exposure(A,B) = c(A,B) / C_A`；`C_A < 30` 只显示数值，不判定“单点依赖”。
6. 若一个 `cited_id` 有多个申请人，它在每个申请人下各计一次；这是“主体级”口径，不是精确企业唯一归属。
7. 页面必须显示：`C_A`、覆盖的外部边数（15,908/407,803）、涉及主体数、时间窗口；结论标“在可映射主体子集内”。

注意：`company_citation_pairs.parquet` 的 `citing_patent_count` 是“A 有多少件专利引用过 B”，不是引用次数，不能直接当 `c(A,B)`。它适合做“引用广度”排行。

## 7. 数据质量标签

- **16 批次**：1,008 行样本显示 14 个批次全为“授权”、2 个批次全为“驳回”；批次按法律状态分层导出，不是随机全量。页面/文档不要称“全量产业数据”。
- **申请人类型**：空值 2,931 行 → 显示“未知”；“境外/未知” 41,319 行保持原样。
- **别名**：393 条，覆盖 9,151 件专利；不是完整实体消解。
- **主题**：`（未细分）` 16,839 行，占主题行 16.1%；不要混入细粒度主题排名。
- **引用**：样本内 7.93%，外部主体覆盖 3.90%；依赖结论必须带样本量。
- **2024—2025**：不完整，不做趋势结论。
