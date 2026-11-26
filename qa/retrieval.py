"""Execute scoped queries and assemble P1 graph/table evidence."""
from collections import defaultdict

import pandas as pd

from core import config
from core.data_loader import load_result, load_table
from core.database import health_check, run_query
from qa import auxiliary, dependency, intents as I, templates as T
from qa.evidence_graph import EvidenceGraph


class QueryUnavailable(RuntimeError):
    pass


class ScopeMismatch(RuntimeError):
    pass


def technical_coverage(patents, topics):
    eligible = patents.loc[patents.patent_type.notna() & ~patents.patent_type.str.contains("外观设计", na=False)]
    return topics.loc[topics.patent_id.isin(eligible.patent_id), "patent_id"].nunique(), len(eligible)


def window(frame, params):
    if params["start_year"] is None:
        return frame
    return frame[frame.apply_year.between(params["start_year"], params["end_year"])]


class Retrieval:
    def __init__(self, intent, slots, entity, aliases, executed):
        self.intent = intent
        self.slots = slots
        self.aliases = aliases
        self.params = {"start_year": slots.get("start_year"), "end_year": slots.get("end_year"),
                       "limit": slots.get("limit", 10), "ipc_scope": slots.get("ipc_scope", "all"),
                       "enterprise_only": slots.get("subject_scope") == "enterprise",
                       "members": list(entity.members) if entity else [],
                       "topic": entity.name if entity and entity.kind == "Technology" else ""}
        self.executed = executed
        self.graph = EvidenceGraph()
        self.patents = load_table("patents")
        self.notes = []
        self.subject = entity.name if entity else ""
        self._graph_verified = False

    def _execute(self, template, params):
        try:
            rows = run_query(template, params, timeout=config.QUERY_TIMEOUT)
        except Exception as exc:
            raise QueryUnavailable("Neo4j 查询失败或超时，请核对连接和当前研究数据范围。") from exc
        if template.strip() not in self.executed:
            self.executed.append(template.strip())
        return rows

    def _verify_graph(self):
        if self._graph_verified:
            return
        if not health_check():
            raise QueryUnavailable("Neo4j 当前不可用，请启动与 USE_SAMPLE 对应的图数据库。")
        ids = sorted(set(self.patents.patent_id.dropna()))
        if not ids:
            raise ScopeMismatch("当前数据范围没有可校验的专利 ID。")
        probes = ids if len(ids) <= 512 else [ids[i * (len(ids) - 1) // 63] for i in range(64)]
        row, = self._execute(T.SCOPE, {"probes": probes})
        if row["patents"] != len(ids) or row["matched"] != len(probes):
            raise ScopeMismatch("Neo4j 的专利数量或校验 ID 与 USE_SAMPLE 选择的数据不一致。")
        self._graph_verified = True

    def query(self, template, **values):
        self._verify_graph()
        return self._execute(template, {**self.params, **values})

    @property
    def graph_verified(self):
        return self._graph_verified

    def matching_result(self, name):
        frame = load_result(name)
        counts = frame.attrs.get("metrics_manifest", {}).get("source_rows", {})
        tables = ("patents", "applicants", "citations") if name == "company_metrics" else ("patents", "patent_topic")
        for table in tables:
            actual = len(self.patents) if table == "patents" else len(load_table(table))
            if counts.get(table) != actual:
                raise auxiliary.DataUnavailable(f"{name} 与当前 P1 源表行数不一致，需要 P1 更新及核对清单。")
        return frame

    def retrieve(self):
        if self.intent in I.RANKED_SUBJECTS:
            self.notes.append("主体范围为 P1 标注为企业的申请人；该分类包含非整车制造商。"
                              if self.params["enterprise_only"] else "主体范围为当前数据集全部申请人。")
        handlers = {I.INFLUENCE: self.influence, I.COOP: self.cooperation, I.LAYOUT: self.cooperation,
                    I.TREND: self.trends, I.GROWTH: self.trends, I.CITATION: self.citations,
                    I.DEPENDENCY: self.citations}
        handler = handlers.get(self.intent)
        return handler() if handler else self.graph_rows()

    def influence(self):
        metric = self.slots["metric"]
        try:
            metrics = self.matching_result("company_metrics")
        except (OSError, ValueError, auxiliary.DataUnavailable):
            if metric != "cited_count":
                raise auxiliary.DataUnavailable("当前 P1 数据范围缺少有效的 company_metrics，请由 P1 补交该范围的预计算指标。")
            self.notes.append("来源为 Neo4j 样本内引用网络，按唯一专利对计算主体被引次数。")
            return self.query(T.INFLUENCE)
        self.notes.append("来源为 P1 company_metrics，统计范围为样本内引用网络，覆盖整个选定数据集。")
        if not metrics.attrs["metrics_manifest"].get("edge_count"):
            self.notes.append("当前样本内主体网络没有引用边，网络指标缺少关系证据。")
        if self.params["enterprise_only"]:
            applicants = load_table("applicants").dropna(subset=["applicant_std", "applicant_type"])
            applicants = applicants[applicants.applicant_type.str.strip().ne("")]
            # Match the P1 graph importer's per-name modal type, including its tie-break.
            mode = applicants.groupby("applicant_std").applicant_type.agg(lambda labels: labels.value_counts().index[0])
            metrics = metrics[metrics.applicant_std.isin(mode[mode.eq("企业")].index)]
        return (metrics.dropna(subset=[metric]).sort_values([metric, "applicant_std"], ascending=[False, True])
                .head(self.params["limit"]).to_dict("records"))

    def graph_rows(self):
        rows = self.query(T.QUERIES[self.intent])
        self.notes.append({
            I.TOP: "来源为 Neo4j，按实际申请人节点统计去重专利数，使用图谱原名。",
            I.IPC: "来源为 Neo4j 非外观设计 IPC，按每分类去重专利；一件专利可归入多个分类。",
            I.TOPICS: "来源为 Neo4j 的主体—专利—主题—领域路径，按主题和领域去重专利。",
            I.PATENTS: "来源为 Neo4j，依次按样本内被引次数降序、申请年降序和专利 ID 升序选取。",
            I.TOPIC_APPLICANTS: "来源为 Neo4j 指定主题关联专利，按申请人去重专利；未细分主题与细分主题各自统计。",
        }[self.intent])
        if self.intent == I.IPC:
            self.notes.append("IPC 范围为主分类。" if self.slots["ipc_scope"] == "main" else "IPC 范围包含主分类和副分类。")
        for row in rows[:10]:
            if self.intent == I.IPC:
                witness = row["evidence"]
                self.graph.edge("APPLIES_FOR", witness["applicant"], witness["patent"])
                self.graph.edge("HAS_IPC", witness["patent"], row["ipc_code"])
            elif self.intent == I.TOPICS:
                witness = row["evidence"]
                self.graph.edge("APPLIES_FOR", witness["applicant"], witness["patent"])
                self.graph.technology(witness["patent"], row["topic"], row["domain"])
            elif self.intent == I.PATENTS:
                for name in row["applicants"][:5]:
                    self.graph.edge("APPLIES_FOR", name, row["patent_id"])
            elif self.intent == I.TOPIC_APPLICANTS:
                self.graph.edge("APPLIES_FOR", row["applicant_std"], row["patent"])
                self.graph.edge("INVOLVES", row["patent"], self.params["topic"])
        return rows

    def cooperation(self):
        date_filtered = self.params["start_year"] is not None
        merged = auxiliary.merged_cooperation() if not date_filtered else None
        partners = {}
        if merged is not None and not merged.empty:
            left = merged.loc[merged.app_a.eq(self.subject), ["app_b", "weight"]].rename(columns={"app_b": "partner"})
            right = merged.loc[merged.app_b.eq(self.subject), ["app_a", "weight"]].rename(columns={"app_a": "partner"})
            rows = (pd.concat([left, right]).sort_values(["weight", "partner"], ascending=[False, True])
                    .head(self.params["limit"]).to_dict("records"))
            catalog = defaultdict(list)
            for name in load_table("applicants").applicant_std.dropna().unique():
                catalog[self.aliases.get(name, name)].append(name)
            for row in rows:
                partners[row["partner"]] = catalog[row["partner"]]
            partner_names = sorted({name for names in partners.values() for name in names})
            for edge in self.query(T.COOP_EVIDENCE, partners=partner_names, evidence_limit=50):
                self.graph.edge("CO_APPLIED_WITH", edge["applicant"], edge["partner"], edge["weight"])
            self.notes.append("合作权重来自 P1 展示层别名合并表，权重为原始合作边权重相加，证据图保留 Neo4j 图谱实际申请人及原边权重。")
            source = "P1 cooperation_merged"
        else:
            if date_filtered or len(self.params["members"]) > 1:
                rows = self.query(T.COOP_WINDOW)
                for row in rows[:10]:
                    edge = row["evidence"]
                    for name in (edge["applicant"], edge["partner"]):
                        self.graph.edge("APPLIES_FOR", name, edge["patent"])
            else:
                rows = self.query(T.COOP)
                for row in rows[:10]:
                    for edge in row["evidence"]:
                        self.graph.edge("CO_APPLIED_WITH", edge["applicant"], edge["partner"], edge["weight"])
            partners = {row["partner"]: [row["partner"]] for row in rows}
            self.notes.append("合作来源为 Neo4j，合作伙伴使用图谱原名，权重为共同申请的去重专利数。")
            source = "Neo4j"
        for row in rows:
            row["cooperation_source"] = source
        if self.intent == I.COOP or not rows:
            return rows
        # A merged display partner can have several graph nodes. Report each
        # actual graph node's layout separately to avoid double-counting patents.
        partner_names = sorted({name for names in partners.values() for name in names})
        layouts = defaultdict(list)
        for offset in range(0, len(partner_names), 50):
            batch = partner_names[offset:offset + 50]
            for item in self.query(T.LAYOUT, partners=batch, evidence_limit=3 * len(batch)):
                layouts[item["partner"]].append(item)
        output = []
        for row in rows:
            names = partners[row["partner"]]
            items = [item for name in names for item in layouts[name]]
            for item in items:
                output.append({**row, **item, "partner": row["partner"], "partner_graph_name": item["partner"]})
                if len(output) <= 20:
                    self.graph.edge("APPLIES_FOR", item["partner"], item["patent"])
                    self.graph.technology(item["patent"], item["topic"], item["domain"])
            if not items:
                output.append({**row, "topic": None, "domain": None, "patent_count": None})
        self.notes.append("布局按合作伙伴的实际申请人节点展示至多三个非外观设计技术主题；缺失主题标为未知。")
        return output

    def trends(self):
        patents = window(self.patents, self.params)
        topics = load_table("patent_topic")
        covered, eligible = technical_coverage(patents, topics)
        coverage = covered / eligible if eligible else None
        start, end = self.params["start_year"], self.params["end_year"]
        try:
            annual = self.matching_result("topic_year")
            annual = annual[annual.year.between(start, end)]
            source = "P1 topic_year"
        except (OSError, ValueError, auxiliary.DataUnavailable):
            technical = patents.loc[patents.patent_type.notna() & ~patents.patent_type.str.contains("外观设计", na=False)]
            base = topics.merge(technical[["patent_id", "apply_year"]], on="patent_id").drop_duplicates(
                ["patent_id", "topic", "domain", "apply_year"])
            annual = base.groupby(["topic", "domain", "apply_year"]).size().rename("count").reset_index()
            annual = annual.rename(columns={"apply_year": "year"})
            source = "P1 patent_topic + patents"
        self.notes.append(f"来源为 {source}，按申请年统计技术类专利，主题覆盖 {covered}/{eligible} 件。")
        columns = {"topic_coverage": coverage, "topic_covered_patents": covered, "technical_patents": eligible}
        if self.intent == I.TREND:
            topic = self.params["topic"]
            annual = annual[annual.topic.eq(topic)]
            if not eligible or not covered:
                return []
            counts = annual.groupby("year")["count"].sum()
            groups = sorted(topics.loc[topics.topic.eq(topic), "domain"].dropna().unique())
            self.notes.append("窗口内未观察到该主题的年份补零；零表示当前范围记录数。")
            return [{"topic": topic, "domain": "、".join(groups) or None, "year": year,
                     "count": int(counts.get(year, 0)), **columns} for year in range(start, end + 1)]
        result = []
        for topic, group in annual.groupby("topic"):
            if topic.endswith(("（未细分）", "(未细分)")):
                continue
            counts = group.groupby("year")["count"].sum()
            initial, final = int(counts.get(start, 0)), int(counts.get(end, 0))
            if initial < 5:
                continue
            result.append({"topic": topic, "domain": "、".join(sorted(group.domain.dropna().unique())) or None,
                           "patent_count": int(counts.sum()), "start_count": initial,
                           "end_count": final, "growth_rate": (final - initial) / initial, **columns})
        self.notes.append("窗口首年至末年的累计增长率=(末年量−首年量)/首年量，首年少于 5 件的主题及未细分主题不参与排名。")
        return sorted(result, key=lambda row: (-row["growth_rate"], -row["patent_count"], row["topic"]))[:self.params["limit"]]

    def _subject_patents(self):
        offset, batch_size = 0, 1000
        while True:
            batch = self.query(T.DEPENDENCY, offset=offset, batch_size=batch_size)
            yield from (r["patent_id"] for r in batch)
            if len(batch) < batch_size:
                return
            offset += batch_size

    def citations(self):
        dependency_intent = self.intent == I.DEPENDENCY
        rows = [] if dependency_intent else self._internal_citations()
        ids = set(self._subject_patents())
        if not ids:
            return rows
        try:
            evidence = dependency.external_evidence(ids, self.aliases)
        except auxiliary.DataUnavailable:
            if dependency_intent:
                raise
            self.notes.append("P1 外部主体明细缺失或不可读，当前结果只覆盖图内 CITES。")
            return rows
        years = self.patents.loc[self.patents.patent_id.isin(ids), "apply_year"].dropna()
        start = self.params["start_year"] or (int(years.min()) if not years.empty else None)
        end = self.params["end_year"] or (int(years.max()) if not years.empty else None)
        external = dependency.external_rows(evidence, self.params["limit"], start, end,
                                            include_topics=dependency_intent, subject=self.subject)
        coverage = evidence.coverage
        coverage_text = f"{coverage:.2%}" if coverage is not None else "无外部边，覆盖率无定义"
        self.notes.append(f"P1 外部明细按当前主体和时间范围匹配到 {evidence.denominator}/{len(evidence.edges)} 条外部专利引用边，覆盖率 {coverage_text}。")
        if dependency_intent:
            self.notes.append("C_A 为可映射外部专利对去重总数，多申请人可各自归属，同一边可进入多个主体，暴露度之和可超过 100%。")
            if evidence.denominator < 30:
                self.notes.append("C_A 小于 30，证据不足以筛选潜在单点依赖。")
            self.notes.append("主题维度仅使用引用方技术主题，外部被引专利的主题与 IPC 未知。")
        else:
            self.notes.append("外部被引专利 IPC、主题及领域未知；图内类型来自被引专利本身。")
        owners = load_table("applicants")[["patent_id", "applicant_std"]].dropna().drop_duplicates()
        owners = owners[owners.applicant_std.isin(self.params["members"]) & owners.patent_id.isin(ids)]
        by_id = owners.groupby("patent_id").applicant_std.min().to_dict()
        for row in external[:10]:
            for path in row["representative_citations"]:
                owner = by_id.get(path["citing_id"])
                if owner:
                    self.graph.citation(owner, path["citing_id"], path["cited_id"], row["applicant_std"])
        if external:
            self.notes.append("图中的外部路径来自 P1 辅助明细，外部专利及其申请关系属于辅助证据。")
        return rows + external

    def _internal_citations(self):
        rows = self.query(T.CITATION)
        chosen = [path["cited"] for row in rows[:10] for path in row["evidence"]]
        if chosen:
            layout = self.query(T.CITATION_LAYOUT, patent_ids=sorted(set(chosen)), evidence_limit=len(chosen))
            by_id = {entry["patent"]: entry for entry in layout}
        else:
            by_id = {}
        for row in rows:
            row.update(citation_scope="样本内", cited_topics=row.pop("topics"),
                       cited_ipc_codes=row.pop("ipc_codes"), cited_domains=row.pop("domains"))
        for row in rows[:10]:
            for path in row["evidence"]:
                self.graph.citation(path["applicant"], path["patent"], path["cited"], row["applicant_std"])
                info = by_id.get(path["cited"], {})
                for code in info.get("ipc_codes", ()):
                    self.graph.edge("HAS_IPC", path["cited"], code)
                for item in info.get("topics", ()):
                    self.graph.technology(path["cited"], item["topic"], item["domain"])
        self.notes.append("样本内数据来自 Neo4j CITES，按被引主体统计去重专利引用边。")
        return rows
