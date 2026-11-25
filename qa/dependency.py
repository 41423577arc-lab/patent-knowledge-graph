"""CQ09/CQ10 external citation evidence from P1's exact edge-level mapping."""
from dataclasses import dataclass

import pandas as pd

from core.data_loader import load_table
from qa.auxiliary import external_applicants

EDGE = ["citing_id", "cited_id"]
PROXY_NOTE = (
    "在可映射外部引证主体子集内，专利引用仅是技术知识关联和依赖暴露的代理指标，"
    "不代表真实商业采购依赖或供应链依赖。"
)


@dataclass
class ExternalEvidence:
    edges: pd.DataFrame
    mapped: pd.DataFrame

    @property
    def denominator(self):
        return len(self.mapped[EDGE].drop_duplicates())

    @property
    def coverage(self):
        return self.denominator / len(self.edges) if len(self.edges) else None


def external_evidence(patent_ids, aliases):
    citations = load_table("citations")
    edges = citations.loc[citations.cited_in_sample.eq(False) & citations.citing_id.isin(patent_ids), EDGE]
    edges = edges.dropna().drop_duplicates()
    mapping = external_applicants().dropna(subset=[*EDGE, "applicant"])
    mapping = mapping[mapping.applicant.str.strip().ne("")]
    # The two-ID join excludes full-only edges from sample mode, including edges
    # whose citing patent happens to appear in both data scopes.
    mapped = edges.merge(mapping, on=EDGE)
    mapped["applicant"] = mapped.applicant.map(lambda value: aliases.get(value, value))
    return ExternalEvidence(edges, mapped.drop_duplicates([*EDGE, "applicant"]))


def external_rows(evidence, limit, start_year, end_year, include_topics=False, subject=None):
    mapped = evidence.mapped
    if subject and not include_topics:
        mapped = mapped[mapped.applicant.ne(subject)]
    denominator = evidence.denominator
    if not denominator:
        return []
    ranking = (mapped.groupby("applicant").size().rename("citation_count").reset_index()
               .sort_values(["citation_count", "applicant"], ascending=[False, True]))
    topics = topic_breakdown(mapped) if include_topics else {}
    rows = []
    for name, count in ranking.head(limit).itertuples(index=False, name=None):
        pairs = (mapped.loc[mapped.applicant.eq(name), EDGE].sort_values(EDGE).head(3)
                 .to_dict("records"))
        row = {"applicant_std": name, "citation_count": count, "citation_scope": "外部引证",
               "representative_citations": pairs, "external_edges": len(evidence.edges),
               "mapped_external_edges": denominator, "applicant_coverage": evidence.coverage,
               "cited_topics": None, "cited_ipc_codes": None, "cited_domains": None}
        if include_topics:
            row.update(C_A=denominator, c_AB=count, dependency_exposure=count / denominator,
                       potential_single_point=denominator >= 30 and 2 * count >= denominator,
                       single_point_assessed=denominator >= 30, involved_applicants=len(ranking),
                       same_display_applicant=name == subject,
                       start_year=start_year, end_year=end_year,
                       citing_topic_exposure=topics.get(name, []))
        rows.append(row)
    return rows


def topic_breakdown(mapped):
    tags = load_table("patent_topic")[["patent_id", "topic"]].dropna().drop_duplicates()
    tagged = mapped.merge(tags, left_on="citing_id", right_on="patent_id")
    denominator = tagged.drop_duplicates([*EDGE, "topic"]).groupby("topic").size()
    counts = (tagged.groupby(["applicant", "topic"]).size().rename("count").reset_index()
              .sort_values(["applicant", "count", "topic"], ascending=[True, False, True]))
    result = {}
    for name, topic, count in counts.itertuples(index=False, name=None):
        total = int(denominator[topic])
        result.setdefault(name, []).append({"citing_topic": topic, "citation_count": count,
                                            "C_A_topic": total, "dependency_exposure": count / total})
    return result
