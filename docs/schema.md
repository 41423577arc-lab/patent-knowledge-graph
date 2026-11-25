# Schema 与数据接口契约（P1）

依据 [团队分工](团队分工.md) 契约 A / B / C。这是新版目标契约，现有 Neo4j 旧图谱未迁移。

## 节点与关系

```text
Patent {patent_id, title, abstract, apply_date, apply_year, pub_date,
        patent_type, country, legal_status, is_in_sample}
Applicant {name, raw_names, type, country}
IPC {code, name, level}
Technology {name, keywords, description}
Domain {name, description}

(Applicant)-[:APPLIES_FOR]->(Patent)
(Patent)-[:CITES]->(Patent)
(Patent)-[:HAS_IPC]->(IPC)
(Patent)-[:INVOLVES]->(Technology)
(Technology)-[:BELONGS_TO]->(Domain)
(Applicant)-[:CO_APPLIED_WITH {weight}]-(Applicant)
```

CITES 从引用方指向被引方。共同申请关系逻辑上无向，每对主体只存一条边（名称排序），查询无向匹配，weight 为共同申请的去重专利数。is_in_sample 标识当前导入研究数据内的专利，外部占位节点为 false。

## 约束与索引（P1 导入器待实施）

```cypher
CREATE CONSTRAINT patent_id_v2 IF NOT EXISTS FOR (n:Patent) REQUIRE n.patent_id IS UNIQUE;
CREATE CONSTRAINT applicant_name_v2 IF NOT EXISTS FOR (n:Applicant) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT ipc_code_v2 IF NOT EXISTS FOR (n:IPC) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT technology_name_v2 IF NOT EXISTS FOR (n:Technology) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT domain_name_v2 IF NOT EXISTS FOR (n:Domain) REQUIRE n.name IS UNIQUE;
CREATE INDEX patent_apply_year_v2 IF NOT EXISTS FOR (n:Patent) ON (n.apply_year);
CREATE INDEX patent_country_v2 IF NOT EXISTS FOR (n:Patent) ON (n.country);
```

尚未对数据库执行这些语句。与旧图谱分库或备份后迁移，避免混合两版 Patent 唯一键。

## 七表列定义

| 文件 | 列（顺序固定） |
|---|---|
| patents.parquet | patent_id, title, abstract, apply_date, apply_year, pub_date, patent_type, country, legal_status, is_in_sample |
| applicants.parquet | patent_id, applicant_raw, applicant_std, applicant_type, is_first |
| patent_ipc.parquet | patent_id, ipc_code, is_main |
| patent_topic.parquet | patent_id, topic, domain |
| patent_efficacy.parquet | patent_id, efficacy_l1, efficacy_l2, efficacy_l3 |
| citations.parquet | citing_id, cited_id, cited_in_sample, cited_applicant_std |
| cooperation.parquet | app_a, app_b, weight |

日期为 ISO YYYY-MM-DD 字符串，apply_year 为可空整数，标志为可空布尔，weight 为正整数，其余为字符串。缺失留 null，不伪造数据。country 是公开国别，不替代 Applicant.country。被引主体为可空单主体标量，无法确定唯一主体时留空；多申请人依赖分析沿图关系取完整集合。

`USE_SAMPLE=true` 读 `data/_sample/`，false 读 `data/processed/`，同名同列、不静默回退。当前样例主题 / 功效两表为空，旧日期混合公开 / 申请 / 优先权，不可映射申请年。

## 只读接口

```python
run_query(cypher: str, params: dict | None = None, timeout: float = 10.0) -> list[dict]
health_check() -> bool
load_table(name: str) -> pandas.DataFrame
load_result(name: str) -> pandas.DataFrame
available_tables() -> list[str]
```

配置键见 core/config.py 与 .env.example，包含契约 B 全部键。只接受可信预置参数化 Cypher，READ_ACCESS 是路由提示，数据库权限须用只读账号保障。超时取调用值与 QUERY_TIMEOUT 的较小值。断连时 health_check 返回 false，run_query 报错供页面处理。

## 预计算结果契约（P1）

| 名称 | 列（顺序固定） |
|---|---|
| company_metrics | applicant_std, patent_count, cited_count, pagerank, degree, betweenness |
| topic_year | topic, domain, year, count |

USE_SAMPLE=true 读取 data/_sample/results/，false 读取 data/results/。两目录均含 company_metrics.parquet、topic_year.parquet 与 metrics_manifest.json。load_result 只接受上述名称，校验列、行数、文件 SHA-256 与 manifest.scope（sample / full），拒绝混合版本，不回退另一范围。DataFrame.attrs 暴露 scope 与指标清单，供使用方展示。全量结果不提交 Git。

### 计算口径

- 输入：当前范围 patents.is_in_sample=true 的专利；申请人按 (patent_id, applicant_std) 去重。
- patent_count：该主体关联的去重专利数；主体可能为企业、高校等，不保证均为企业。
- cited_count：当前范围内引用 / 被引两端均有专利的去重 (citing_id, cited_id) 对数，按被引专利申请人汇总，含主体自引；不使用来源文件的累计被引数字，不计外部占位专利。
- 引用网络：主体为节点，方向为引用方主体→被引方主体。每个专利引用对扩展到双方申请人组合，每个不同主体组合加权 1；排除主体自环。共同申请专利的每个主体分别获得完整关系计数，不能把主体计数相加当作专利总数。
- pagerank：上述有向加权网络，alpha=0.85，包括孤立主体。无边且非空时为均匀分布。
- degree：网络转无向后的去重邻居数 / (N−1)，不是原始边数；N≤1 时为 0。
- betweenness：有向网络、不用边权距离、标准化最短路径中介中心性。N≤500 精确计算；更大网络固定 seed=42、k=128 抽样近似。manifest 记录计算方式，近似值不能称为精确值。
- topic_year：按 topic / domain / apply_year 分组后的去重 patent_id 数，year 和 count 为整数。只保留非空主题 / 领域及合法整数申请年，不用旧混合日期替代申请年。

scripts/calculate_metrics.py 是唯一指标实现位置。UI 不重复计算。结果清单记录数据范围、源表行数、节点 / 边数、PageRank 参数及中介近似方式；重新清洗后须重算，两张结果表与清单应整体交付。
