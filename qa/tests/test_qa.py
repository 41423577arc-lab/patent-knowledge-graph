from datetime import date
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from core import config
from qa import answer_builder, cache, dependency, intents, llm_client, templates
from qa.entity_linker import Catalog
from qa.evidence_graph import EvidenceGraph
from qa.service import answer


class IntentTests(unittest.TestCase):
    def test_p3_examples(self):
        for intent, question in intents.EXAMPLES.items():
            with self.subTest(intent=intent):
                self.assertEqual(intents.rule_intent(question), intent)

    def test_real_phrasing(self):
        cases = {
            "比亚迪布局了哪些技术领域？": intents.IPC,
            "宁德时代和哪些企业合作申请过专利？": intents.COOP,
            "动力电池热管理这些年的专利数量怎么变？": intents.TREND,
            "比亚迪的合作企业各自布局什么？": intents.LAYOUT,
            "比亚迪的技术依赖外部吗？": intents.DEPENDENCY,
        }
        for question, intent in cases.items():
            with self.subTest(question=question):
                self.assertEqual(intents.rule_intent(question), intent)

    def test_parameters(self):
        for slots in ({"limit": 51}, {"limit": True}, {"limit": "2"}, {"start_year": 2023, "end_year": 2019},
                      {"start_year": 1999.5}, {"unknown": 1}):
            with self.subTest(slots=slots), self.assertRaises(intents.InvalidSlots):
                intents.validate(intents.TOP, slots)
        self.assertEqual(intents.rule_slots("近三年的技术主题增长", intents.GROWTH),
                         {"start_year": 2021, "end_year": 2023})
        self.assertEqual(intents.validate(intents.TREND, {"start_year": 2019, "end_year": 2025})["end_year"], 2023)
        with self.assertRaises(intents.InvalidSlots):
            intents.validate(intents.GROWTH, {"start_year": 2024, "end_year": 2025})

    def test_template_registry(self):
        self.assertEqual(set(templates.QUERIES), set(intents.EXAMPLES))
        for statement in templates.QUERIES.values():
            self.assertIn("LIMIT ", statement)
            self.assertNotRegex(statement, r"\b(CREATE|DELETE|MERGE|SET|REMOVE|DROP|LOAD CSV)\b")


class EntityTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "applicant_std": ["比亚迪股份有限公司", "起亚株式会社", "现代汽车株式会社", "中国南方"],
            "applicant_raw": ["比亚迪股份", "Kia", "Hyundai", "中国南方"],
        })
        self.patcher = patch("qa.entity_linker.load_table", return_value=self.frame)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.catalog = Catalog("applicant", {"比亚迪股份有限公司": "比亚迪", "BYD": "比亚迪"})

    def test_canonical_expands_to_real_graph_name(self):
        entity, candidates = self.catalog.link("BYD 的专利")
        self.assertEqual(entity.members, ("比亚迪股份有限公司",))
        self.assertEqual(entity.name, "比亚迪")
        self.assertFalse(candidates)

    def test_ambiguity_and_clarification(self):
        entity, candidates = self.catalog.link("Kia 和 Hyundai 涉及哪些主题")
        self.assertIsNone(entity)
        self.assertEqual({x["name"] for x in candidates}, {"起亚株式会社", "现代汽车株式会社"})
        entity, _ = self.catalog.link("同一问题最后附加明确候选", "起亚株式会社")
        self.assertEqual(entity.members, ("起亚株式会社",))

    def test_no_unconfirmed_approximate_match(self):
        entity, candidates = self.catalog.link("起亚株式会社a", "起亚株式会社a")
        self.assertIsNone(entity)
        self.assertEqual(candidates[0]["name"], "起亚株式会社")
        self.assertTrue(all(0 <= item["score"] <= 1 for item in candidates))

    def test_topic(self):
        with patch("qa.entity_linker.load_table", return_value=pd.DataFrame({"topic": ["动力电池热管理"]})):
            catalog = Catalog("topic", {})
        self.assertEqual(catalog.link("动力电池热管理年度申请量怎么变")[0].name, "动力电池热管理")
        self.assertIsNone(catalog.link("量子穿梭主题")[0])


class DependencyTests(unittest.TestCase):
    def test_scope_and_edge_deduplication(self):
        citations = pd.DataFrame({"citing_id": ["a", "a", "a", "b"], "cited_id": ["x", "x", "y", "x"],
                                  "cited_in_sample": [False, False, True, False]})
        mapping = pd.DataFrame({"citing_id": ["a", "a", "a", "b"], "cited_id": ["x", "x", "y", "x"],
                                "applicant": ["B", "B alias", "C", "D"]})
        with patch("qa.dependency.load_table", return_value=citations), patch("qa.dependency.external_applicants", return_value=mapping):
            result = dependency.external_evidence(["a"], {"B alias": "B"})
        self.assertEqual(result.denominator, 1)
        self.assertEqual(result.coverage, 1)
        self.assertEqual(result.mapped.applicant.tolist(), ["B"])

    def test_zero_and_threshold(self):
        columns = [*dependency.EDGE, "applicant"]
        empty = pd.DataFrame(columns=columns)
        for size, dominant, expected in ((0, 0, False), (29, 29, False), (30, 15, True), (31, 15, False)):
            with self.subTest(size=size, dominant=dominant):
                mapped = pd.DataFrame(
                    [(f"a{i}", f"x{i}", "B" if i < dominant else f"C{i}") for i in range(size)],
                    columns=columns,
                ) if size else empty
                result = dependency.ExternalEvidence(mapped[dependency.EDGE], mapped)
                with patch("qa.dependency.topic_breakdown", return_value={}):
                    rows = dependency.external_rows(result, 1, 2018, 2023, include_topics=True)
                if size:
                    self.assertEqual(rows[0]["C_A"], size)
                    self.assertEqual(rows[0]["potential_single_point"], expected)
                else:
                    self.assertEqual(rows, [])

    def test_topic_denominator_with_multiple_cited_applicants(self):
        mapped = pd.DataFrame([("a", "b", "B"), ("a", "b", "C"), ("a", "c", "C")],
                              columns=[*dependency.EDGE, "applicant"])
        with patch("qa.dependency.load_table", return_value=pd.DataFrame({"patent_id": ["a"], "topic": ["电池"]})):
            rows = dependency.topic_breakdown(mapped)
        self.assertEqual(rows["B"][0]["dependency_exposure"], 0.5)
        self.assertEqual(rows["C"][0]["dependency_exposure"], 1)


class InterfaceTests(unittest.TestCase):
    def test_empty_unsupported_and_invalid(self):
        with patch.object(config, "QA_BACKEND", "real"):
            for question in ("", "今天吃什么？", "专利申请量最高的创新主体前999名？"):
                with self.subTest(question=question):
                    result = answer(question, "rule")
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["suggestions"])
                    self.assertEqual(result["data"], [])

    def test_unavailable_and_mock_isolation(self):
        with patch("qa.retrieval.load_table", return_value=pd.DataFrame({"patent_id": ["p1"]})), \
             patch("qa.retrieval.health_check", return_value=False), patch("qa.cache.recover", return_value=None):
            q = "专利申请量最高的创新主体有哪些？"
            with patch.object(config, "QA_BACKEND", "real"), patch.object(config, "LLM_API_KEY", ""):
                result = answer(q, "llm")
                self.assertFalse(result["ok"])
                self.assertIn("Neo4j", result["error"])
                self.assertEqual(result["mode"], "rule")
            with patch.object(config, "QA_BACKEND", "mock"):
                self.assertTrue(answer("演示：创新主体申请量排名")["conclusion"].startswith("【演示假数据】"))

    def test_scope_mismatch(self):
        with patch.object(config, "QA_BACKEND", "real"), patch("qa.retrieval.health_check", return_value=True), \
             patch("qa.retrieval.load_table", return_value=pd.DataFrame({"patent_id": ["p1"]})), \
             patch("qa.retrieval.run_query", return_value=[{"patents": 15, "matched": 1}]) as query:
            result = answer(intents.EXAMPLES[intents.TOP], "rule")
        self.assertFalse(result["ok"])
        self.assertIn("USE_SAMPLE", result["error"])
        self.assertEqual(query.call_count, 1)

    def test_graph_and_json(self):
        graph = EvidenceGraph()
        graph.citation("源", "A1", "B1", "目标")
        graph.technology("A1", "电池", "动力")
        graph.citation("源", "A1", "B1", "目标")
        ids = {node["id"] for node in graph.public["nodes"]}
        self.assertEqual(len(ids), len(graph.public["nodes"]))
        self.assertTrue(all({edge["source"], edge["target"]} <= ids for edge in graph.public["edges"]))
        value = answer_builder.json_value({"a": pd.NA, "b": np.float64("nan"), "c": np.int64(2),
                                           "d": date(2020, 1, 1), "e": np.bool_(True), "f": pd.NaT})
        self.assertEqual(value, {"a": None, "b": None, "c": 2, "d": "2020-01-01", "e": True, "f": None})
        json.dumps(value, allow_nan=False)

    def test_cache_scope_and_cypher(self):
        question = "测试缓存隔离"
        with patch.object(config, "USE_SAMPLE", True):
            key = cache.key(question)
            cache.remember(key, {**answer_builder.failure(""), "cypher": "MATCH", "ok": True})
            self.assertEqual(cache.recover(key)["cypher"], "")
        with patch.object(config, "USE_SAMPLE", False):
            self.assertIsNone(cache.recover(cache.key(question)))
        with patch("qa.cache.monotonic", return_value=cache.monotonic() + 901):
            self.assertIsNone(cache.recover(key))


class LlmTests(unittest.TestCase):
    def test_no_api_key(self):
        with patch.object(config, "LLM_API_KEY", ""), self.assertRaises(llm_client.ModelUnavailable):
            llm_client.classify("什么问题")

    def test_invalid_json_and_timeout(self):
        with patch.object(config, "LLM_API_KEY", "unit-test"), patch("openai.OpenAI") as factory:
            create = factory.return_value.__enter__.return_value.chat.completions.create
            create.return_value = SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(content='{"intent":null,"intent":null}'))])
            with self.assertRaises(llm_client.ModelUnavailable):
                llm_client.classify("任何问题")
            self.assertEqual(create.call_args.kwargs["extra_body"]["thinking"]["type"], "disabled")
            create.side_effect = TimeoutError()
            with self.assertRaises(llm_client.ModelUnavailable):
                llm_client.classify("任何问题")

    def test_altered_facts_are_rejected(self):
        with patch("qa.llm_client.complete_json", return_value={"sentences": ["范围。", "999 件。", "口径。"]}):
            with self.assertRaises(llm_client.ModelUnavailable):
                llm_client.organize(["范围。", "2 件。", "口径。"])

    def test_generation_timeout_does_not_requery(self):
        with patch.object(config, "LLM_API_KEY", "unit-test"), patch.object(config, "QA_BACKEND", "real"), \
             patch("qa.llm_client.classify", return_value=(intents.TOP, {})), \
             patch("qa.llm_client.organize", side_effect=llm_client.ModelUnavailable), \
             patch("qa.retrieval.health_check", return_value=True), \
             patch("qa.retrieval.load_table", return_value=pd.DataFrame({"patent_id": ["P1"]})), \
             patch("qa.retrieval.run_query", side_effect=[
                 [{"patents": 1, "matched": 1}], [{"applicant_std": "甲", "patent_count": 1}],
             ]) as query:
            result = answer(intents.EXAMPLES[intents.TOP], "llm")
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "rule")
        self.assertEqual(query.call_count, 2)


if __name__ == "__main__":
    unittest.main()
