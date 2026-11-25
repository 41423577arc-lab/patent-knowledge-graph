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

`USE_SAMPLE=true` 读 `data/_sample/`（481 件真实样例，主题 / 功效已非空），false 读 `data/processed/`，同名同列、不静默回退。样例仅用于开发，规模 / 趋势结论用全量。

## 只读接口

```python
run_query(cypher: str, params: dict | None = None, timeout: float = 10.0) -> list[dict]
health_check() -> bool
load_table(name: str) -> pandas.DataFrame
available_tables() -> list[str]
```

配置键见 core/config.py 与 .env.example，包含契约 B 全部键。只接受可信预置参数化 Cypher，READ_ACCESS 是路由提示，数据库权限须用只读账号保障。超时取调用值与 QUERY_TIMEOUT 的较小值。断连时 health_check 返回 false，run_query 报错供页面处理。
