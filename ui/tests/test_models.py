import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from ui.qa_state import active_turn, clarified_question, failure, initialize, new_conversation, normalize_answer, process_pending, queue_question
from ui.qa_visuals import INTENTS, SCHEMA, build_statistic, graph_figure, metric_cards, validated_graph


def result(intent="Q_TOP_APPLICANTS", rows=None, graph=None):
    answer = failure("")
    answer.update(ok=True, error=None, intent=intent, conclusion="UI 测试数据，不是业务事实", data=rows or [],
                  graph=graph or {"nodes": [], "edges": []}, cypher="RETURN $value AS value")
    return answer


ROWS = {
    "Q_TOP_APPLICANTS": [{"applicant_std": "测试主体 A", "patent_count": 4}],
    "Q_INFLUENTIAL_APPLICANTS": [{"applicant_std": "测试主体 A", "pagerank": .4}],
    "Q_COMPANY_IPC": [{"ipc_code": "H01M", "count": 4}],
    "Q_COOPERATION": [{"partner": "测试主体 B", "weight": 2}],
    "Q_TOPIC_TREND": [{"year": 2022, "count": 5}, {"year": 2023, "count": 9}],
    "Q_GROWTH_TOPICS": [{"topic": "测试主题", "growth_rate": .3, "patent_count": 4}],
    "Q_COMPANY_TOPICS_DOMAIN": [{"topic": "测试主题", "patent_count": 4}],
    "Q_COOP_LAYOUT": [{"applicant_std": "测试主体 B", "patent_count": 4}],
    "Q_CITATION_APPLICANTS": [{"target_applicant": "测试主体 B", "citation_count": 3}],
    "Q_DEPENDENCY_EXPOSURE": [{"target_applicant": "测试主体 B", "dependency_exposure": .6, "C_A": 5}],
    "Q_COMPANY_PATENTS": [{"patent_id": "UI-TEST", "title": "UI 测试专利"}],
    "Q_TOPIC_APPLICANTS": [{"applicant_std": "测试主体 A", "patent_count": 4}],
}


class StateTests(unittest.TestCase):
    def test_single_submission_history_and_new_conversation(self):
        state = initialize({})
        self.assertFalse(queue_question(state, " \n ", "auto", "mock", "sample"))
        self.assertTrue(queue_question(state, "完整中文问题\n第二行", "auto", "real", "full"))
        self.assertFalse(queue_question(state, "重复点击", "auto", "real", "full"))
        calls = []
        def service(question, mode):
            calls.append((question, mode)); return result(rows=ROWS["Q_TOP_APPLICANTS"])
        self.assertTrue(process_pending(state, service))
        self.assertFalse(process_pending(state, service))
        self.assertEqual(len(calls), 1)
        saved = active_turn(state)
        self.assertEqual(saved["scope"], "full")
        self.assertEqual(saved["question"], "完整中文问题\n第二行")
        self.assertEqual(saved["answer"]["data"], ROWS["Q_TOP_APPLICANTS"])
        new_conversation(state)
        self.assertEqual(state["turns"], [])
        self.assertIsNone(active_turn(state))

    def test_exception_and_timeout_do_not_expose_secrets_or_drop_question(self):
        for exception in [TimeoutError("password=secret"), RuntimeError("api_key=secret")]:
            state = initialize({}); queue_question(state, "完整问题", "auto", "real", "full")
            def service(*args, **kwargs): raise exception
            process_pending(state, service)
            self.assertFalse(state["busy"])
            self.assertEqual(state["draft"], "完整问题")
            self.assertNotIn("secret", json.dumps(state, ensure_ascii=False))
            self.assertIsNone(active_turn(state)["reported_mode"])

    def test_normalization_and_confirmation(self):
        self.assertFalse(normalize_answer({"mode": []})["ok"])
        raw = result(); normalized = normalize_answer(raw); normalized["data"].append({})
        self.assertEqual(raw["data"], [])
        turn = {"question": "模糊主体有哪些专利？", "answer": result()}
        candidate = {"slot": "applicant", "name": "确认主体", "id": "a", "type": "Applicant", "score": .8}
        self.assertIn("确认主体", clarified_question(turn, candidate))
        self.assertEqual(turn["question"], "模糊主体有哪些专利？")


class VisualTests(unittest.TestCase):
    def test_all_intents_render_only_returned_numbers(self):
        self.assertEqual(set(ROWS), set(INTENTS))
        for intent, rows in ROWS.items():
            with self.subTest(intent=intent):
                answer = result(intent, rows)
                snapshot = deepcopy(answer)
                figure, _ = build_statistic(answer)
                self.assertEqual(answer, snapshot)
                self.assertEqual(figure is not None, intent != "Q_COMPANY_PATENTS")

    def test_missing_values_and_exposure_are_not_fabricated(self):
        self.assertIsNone(build_statistic(result("Q_TOPIC_TREND", [{"count": 9}]))[0])
        bad = result("Q_DEPENDENCY_EXPOSURE", [{"target_applicant": "A", "dependency_exposure": 60}])
        self.assertIsNone(build_statistic(bad)[0]); self.assertEqual(metric_cards(bad), [])
        answer = result(rows=[{"applicant_std": "A", "patent_count": None}, {"applicant_std": "B", "patent_count": 3}])
        figure, _ = build_statistic(answer)
        self.assertEqual(list(figure.data[0].x), [3])

    def test_schema_directions_arrows_and_no_placeholder_nodes(self):
        nodes = [{"id": kind, "label": kind, "type": kind} for kind in ["Applicant", "Patent", "IPC", "Technology", "Domain"]]
        nodes.append({"id": "other", "label": "Other", "type": "Applicant"})
        edges = [{"source": source, "target": target if kind != "CO_APPLIED_WITH" else "other", "type": kind, "weight": 1}
                 for kind, (source, target) in SCHEMA.items()]
        edges.append({"source": "missing", "target": "Patent", "type": "APPLIES_FOR"})
        edges.append({"source": "Patent", "target": "Applicant", "type": "APPLIES_FOR"})
        graph = {"nodes": nodes, "edges": edges}
        clean_nodes, clean_edges, warnings = validated_graph(graph)
        self.assertEqual(len(clean_nodes), 6); self.assertEqual(len(clean_edges), 6); self.assertTrue(warnings)
        figure, _ = graph_figure(graph)
        self.assertEqual(len(figure.layout.annotations), 5)  # all directed relations, no arrow on co-application
        self.assertEqual(graph["edges"], edges)

    def test_original_assets_match_delivery_manifest(self):
        folder = Path(__file__).resolve().parents[1] / "assets"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        for relative, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((folder / relative).read_bytes()).hexdigest(), digest, relative)


if __name__ == "__main__":
    unittest.main()
