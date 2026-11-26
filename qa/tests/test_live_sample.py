"""Opt-in integration checks for the P1 481-patent development graph."""
import json
import os
import unittest
from unittest.mock import patch

from core import config
from core.data_loader import load_table
from qa import intents as I
from qa.service import answer

QUESTIONS = {
    I.TOP: I.EXAMPLES[I.TOP],
    I.INFLUENCE: I.EXAMPLES[I.INFLUENCE],
    I.IPC: "「国家电网」布局了哪些 IPC 技术领域？",
    I.COOP: "「中国南方」与哪些主体共同申请过专利？",
    I.TREND: "「驱动电机」的年度申请量如何变化？",
    I.GROWTH: "2015–2023 年哪些技术主题增长最快？",
    I.TOPICS: "「国家电网」涉及哪些技术主题和领域？",
    I.LAYOUT: "「中国南方」的合作主体各自布局什么技术？",
    I.CITATION: "「国家电网」引用了哪些主体的专利？",
    I.DEPENDENCY: "「国家电网」的技术引用是否集中于少数外部主体？",
    I.PATENTS: "「国家电网」的代表性专利有哪些？",
    I.TOPIC_APPLICANTS: "「驱动电机」技术主题的主要创新主体是谁？",
}


@unittest.skipUnless(os.getenv("P2_LIVE_SAMPLE") == "1", "Set P2_LIVE_SAMPLE=1 for the P1 sample graph")
class LiveSampleTests(unittest.TestCase):
    def test_all_intents_against_p1_sample(self):
        self.assertTrue(config.USE_SAMPLE)
        self.assertEqual(load_table("patents").patent_id.nunique(), 481)
        with patch.object(config, "QA_BACKEND", "real"):
            for intent, question in QUESTIONS.items():
                with self.subTest(intent=intent):
                    result = answer(question, mode="rule")
                    self.assertTrue(result["ok"], result["error"])
                    self.assertEqual(result["intent"], intent)
                    self.assertEqual(result["mode"], "rule")
                    self.assertTrue(result["data"])
                    self.assertIsNone(result["error"])
                    json.dumps(result, ensure_ascii=False, allow_nan=False)
                    nodes = {node["id"] for node in result["graph"]["nodes"]}
                    if intent in {I.TOPICS, I.LAYOUT, I.CITATION, I.DEPENDENCY}:
                        self.assertTrue(result["graph"]["edges"])
                    for edge in result["graph"]["edges"]:
                        self.assertTrue({edge["source"], edge["target"]} <= nodes)
                        self.assertGreaterEqual(edge["weight"], 0)
                    if intent == I.DEPENDENCY:
                        row = result["data"][0]
                        self.assertEqual((row["c_AB"], row["C_A"], row["external_edges"]), (2, 6, 114))
                        self.assertAlmostEqual(row["dependency_exposure"], 1 / 3)
                        self.assertFalse(row["single_point_assessed"])


if __name__ == "__main__":
    unittest.main()
