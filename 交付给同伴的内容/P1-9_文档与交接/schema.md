# Schema 与数据接口契约（P1）

依据 [团队分工](团队分工.md) 契约 A / B / C。全量契约图已导入 Neo4j Desktop 本地实例（2026.10.2），计数与校验见 `data/results/scale.json`。

## 节点与关系

```text
Patent {patent_id, title, abstract, apply_date, apply_year, pub_date,
        patent_type, country, legal_status, is_in_sample}
Applicant {name, raw_names, type, country}
IPC {code, name, level}
Technology {name, keywords, description}
Domain {name, description}

(Applicant)-[:APPLIES_FOR {is_first}]->(Patent)
(Patent)-[:CITES]->(Patent)
(Patent)-[:HAS_IPC {is_main}]->(IPC)
(Patent)-[:INVOLVES]->(Technology)
(Technology)-[:BELONGS_TO]->(Domain)
(Applicant)-[:CO_APPLIED_WITH {weight}]-(Applicant)
```

CITES 从引用方指向被引方。共同申请关系逻辑上无向，每对主体只存一条边（名称排序），查询无向匹配，weight 为共同申请的去重专利数。is_in_sample 标识当前导入研究数据内的专利，外部占位节点为 false。

全量导入计数（2026-11-25，Neo4j 2026.10.2）：

| 类型 | 名称 | 数量 |
|---|---|---:|
| 节点 | Patent | 106,393 |
| 节点 | Applicant | 27,557 |
| 节点 | IPC | 13,166 |
| 节点 | Technology | 50 |
| 节点 | Domain | 8 |
| 关系 | APPLIES_FOR | 115,927 |
| 关系 | CITES（仅样本内） | 35,114 |
| 关系 | HAS_IPC | 306,023 |
| 关系 | INVOLVES | 104,723 |
| 关系 | BELONGS_TO | 50 |
| 关系 | CO_APPLIED_WITH | 9,826 |

CITES 只导入 `cited_in_sample=true` 的 35,114 条；外部 407,803 条不建占位节点，企业级引用用 `external_citation_applicants.parquet` 聚合。

## 约束与索引（已执行）

```cypher
CREATE CONSTRAINT patent_id_v2 IF NOT EXISTS FOR (n:Patent) REQUIRE n.patent_id IS UNIQUE;
CREATE CONSTRAINT applicant_name_v2 IF NOT EXISTS FOR (n:Applicant) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT ipc_code_v2 IF NOT EXISTS FOR (n:IPC) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT technology_name_v2 IF NOT EXISTS FOR (n:Technology) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT domain_name_v2 IF NOT EXISTS FOR (n:Domain) REQUIRE n.name IS UNIQUE;
CREATE INDEX patent_apply_year_v2 IF NOT EXISTS FOR (n:Patent) ON (n.apply_year);
CREATE INDEX patent_country_v2 IF NOT EXISTS FOR (n:Patent) ON (n.country);
```

已由 `scripts/build_graph.py` 在导入前创建并等待索引上线；`scale.json` 保存 `SHOW CONSTRAINTS` / `SHOW INDEXES` 的实际结果。

## 图导入

```bash
python -m scripts.build_graph          # 全量 processed
python -m scripts.build_graph --reset  # 重建前清空契约图
python -m scripts.build_graph --sample # 样例（需 --reset）
```

导入器会先检查契约标签是否已有节点；非空且未加 `--reset` 时直接退出，避免重复建边。导入后逐项核对节点和关系计数，任何一项与 parquet 不一致都会失败。

节点属性现状：`Applicant.country` 为空（七表没有申请人国家字段）；`IPC.name` 为空、`level` 由代码长度推断；`Technology.keywords` 为空列表、`description` 为空；`Domain.description` 为空。没有伪造缺失属性。

## 展示层辅助表（非契约 C）

这些表不改变七表契约，也不自动写入 Neo4j；P2/P3 读取时需标明“展示层/聚合”。

| 文件 | 列 | 用途 |
|---|---|---|
| `company_alias.csv` | alias, canonical, method, rows | 企业别名 → 规范名；method = manual / auto_en / pending_review |
| `cooperation_merged.parquet` | app_a, app_b, weight, raw_pairs | 按 canonical 合并的合作边；自环已删 |
| `company_patent_counts.csv` | canonical, patent_count, applicant_rows, alias_count, share_pct | 合并后企业专利数 |
| `company_citation_pairs.parquet` | citing_company, cited_company, citing_patent_count | 企业级引用聚合（口径 C） |
| `topic_quality.csv` | topic, domain, patent_count, is_fallback, share_pct_of_tech_patents | 主题计数与 `（未细分）` 标记 |

规则：Kia 与 Hyundai **不合并**；`中国南方` 是 `pending_review`，不硬并；别名不是完整实体消解；企业级引用是“引用集合里出现过”的聚合，不是精确专利边。`citations.parquet` / `cooperation.parquet` / `applicants.parquet` 保持原样。

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
