# 七表契约校验（P1-5）

状态：**PASS**
生成时间：2026-11-25T15:45:10

数据目录：`data/processed/`（USE_SAMPLE=false）

## 校验项

| 检查 | 状态 | 详情 |
|---|---|---|
| seven_tables_available | pass | available=['applicants', 'citations', 'cooperation', 'patent_efficacy', 'patent_ipc', 'patent_topic', 'patents'] |
| patents_columns | pass | rows=106393, cols=10 |
| applicants_columns | pass | rows=115927, cols=5 |
| patent_ipc_columns | pass | rows=306023, cols=3 |
| patent_topic_columns | pass | rows=104723, cols=3 |
| patent_efficacy_columns | pass | rows=391642, cols=4 |
| citations_columns | pass | rows=442917, cols=4 |
| cooperation_columns | pass | rows=9826, cols=3 |
| patents_patent_id_unique | pass | rows=106393, unique=106393 |
| patents_patent_id_nonnull | pass | null=0 |
| applicants_fk | pass | orphans=0 |
| applicants_required_nonnull | pass | nulls={'patent_id': 0, 'applicant_std': 0, 'is_first': 0} |
| applicants_no_duplicate_pair | pass | dups=0 |
| applicants_one_first_per_patent | pass | groups=106353, bad=0 |
| ipc_fk | pass | orphans=0 |
| ipc_required_nonnull | pass | nulls={'patent_id': 0, 'ipc_code': 0, 'is_main': 0} |
| ipc_no_duplicate_pair | pass | dups=0 |
| ipc_at_most_one_main | pass | groups=85946, bad=0 |
| topic_fk | pass | orphans=0 |
| topic_required_nonnull | pass | nulls={'patent_id': 0, 'topic': 0, 'domain': 0} |
| topic_no_duplicate_pair | pass | dups=0 |
| efficacy_fk | pass | orphans=0 |
| efficacy_required_nonnull | pass | null patent_id=0 |
| efficacy_has_content | pass | empty_rows=0 |
| efficacy_no_duplicate_triple | pass | dups=0 |
| citations_citing_fk | pass | orphans=0 |
| citations_true_cited_fk | pass | orphans=0 |
| citations_false_not_in_sample | pass | overlap=0 |
| citations_no_duplicate_edge | pass | dups=0 |
| cooperation_fk | pass | orphans_a=0, orphans_b=0 |
| cooperation_order | pass | app_a < app_b |
| cooperation_weight_positive | pass | min=1, max=553 |
| cooperation_no_duplicate_pair | pass | dups=0 |
| dtypes | pass | {'patents.apply_year': 'Int64', 'patents.is_in_sample': 'bool', 'applicants.is_first': 'boolean', 'patent_ipc.is_main': 'boolean', 'citations.cited_in_sample': 'boolean', 'cooperation.weight': 'int64'} |

## 规模

| 指标 | 数值 |
|---|---:|
| patents | 106393 |
| patents_by_type | 发明授权:42678, 实用新型:24511, 发明申请:19625, 外观设计:19579 |
| design_patents | 19579 |
| non_design_patents | 86814 |
| applicants_rows | 115927 |
| unique_applicants | 27557 |
| patents_with_applicants | 106353 |
| patent_ipc_rows | 306023 |
| unique_ipc | 13166 |
| patents_with_ipc | 85946 |
| patent_topic_rows | 104723 |
| unique_topics | 50 |
| unique_domains | 8 |
| patents_with_topic | 71487 |
| patent_efficacy_rows | 391642 |
| patents_with_efficacy | 77617 |
| citations_rows | 442917 |
| citations_in_sample | 35114 |
| citations_external | 407803 |
| citations_with_applicant | 41395 |
| cooperation_rows | 9826 |
| cooperation_max_weight | 553 |

## 警告与说明

- 82 件专利没有 is_main=True 的 IPC
- 40 件专利没有申请人
- 868 件非外观设计没有 IPC
- 15327 件非外观设计没有主题
- 9197 件非外观设计没有功效
- 2931 条申请关系 applicant_type 为空
- 引用边 442,917；样本内 35,114；外部 407,803
- P1-5 只校验契约结构；数据质量抽样与别名表在 P1-8 处理。
