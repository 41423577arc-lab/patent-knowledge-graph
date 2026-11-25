"""Native Streamlit tests through the real app entrypoint and public service seam."""
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from core import config

from ui.qa_state import failure
from ui.tests.test_models import ROWS, result

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def button(app, key):
    return next(item for item in app.button if item.key == key)


def open_workbench():
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    app.switch_page("pages/03_智能问答与关联路径.py").run()
    return app


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        for name, value in [("USE_SAMPLE", True), ("QA_BACKEND", "mock")]:
            setting = patch.object(config, name, value)
            setting.start()
            self.addCleanup(setting.stop)

    def test_native_pages_and_real_service_mock_examples(self):
        app = AppTest.from_file(APP_PATH, default_timeout=45).run()
        self.assertFalse(app.exception)
        for path in ["pages/01_产业技术全景.py", "pages/02_创新主体与合作网络.py", "pages/03_智能问答与关联路径.py"]:
            app.switch_page(path).run(); self.assertFalse(app.exception, app.exception)
        for question in ["演示：创新主体申请量排名", "演示：主体 A 的代表性专利", "演示：主体 A 的依赖暴露度"]:
            app.chat_input[0].set_value(question).run()
            self.assertFalse(app.exception, app.exception)
            self.assertTrue(app.session_state["ev_qa"]["turns"][-1]["answer"]["ok"])

    def test_history_rerun_view_and_new_session(self):
        app = open_workbench()
        for question in ["演示：创新主体申请量排名", "演示：主体 A 的依赖暴露度"]:
            app.chat_input[0].set_value(question).run()
        self.assertFalse(app.exception)
        turns = deepcopy(app.session_state["ev_qa"]["turns"])
        app.run()
        self.assertEqual(len(app.session_state["ev_qa"]["turns"]), 2)
        button(app, f'ev_history_{turns[0]["id"]}').click().run()
        self.assertEqual(app.session_state["ev_qa"]["active_id"], turns[0]["id"])
        self.assertEqual(app.session_state["ev_qa"]["turns"][0]["answer"], turns[0]["answer"])
        button(app, "ev_qa_new").click().run()
        self.assertFalse(app.exception); self.assertEqual(app.session_state["ev_qa"]["turns"], [])

    def test_example_only_prefills_until_explicit_submit(self):
        app = open_workbench()
        with patch("qa.service.answer", return_value=result(rows=ROWS["Q_TOP_APPLICANTS"])) as service:
            button(app, "ev_example_0").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["ev_qa"]["turns"], [])
            service.assert_not_called()
            app.chat_input[0].set_value("演示：创新主体申请量排名").run()
            service.assert_called_once()

    def test_all_intents_and_empty_unknown_timeout_states(self):
        app = open_workbench()
        for intent, rows in ROWS.items():
            with self.subTest(intent=intent), patch("qa.service.answer", return_value=result(intent, rows)) as service:
                app.chat_input[0].set_value(f"UI 测试 {intent}").run()
                self.assertFalse(app.exception, app.exception)
                self.assertEqual(app.session_state["ev_qa"]["turns"][-1]["answer"]["intent"], intent)
                service.assert_called_once()
        for response in [result(), failure("未匹配意图"), failure("未找到实体"), failure("查询超时")]:
            with patch("qa.service.answer", return_value=response):
                app.chat_input[0].set_value("状态测试").run()
                self.assertFalse(app.exception, app.exception)
        with patch("qa.service.answer", side_effect=TimeoutError("private-secret")):
            app.chat_input[0].set_value("超时测试").run()
            self.assertFalse(app.exception); self.assertNotIn("private-secret", str(app.session_state["ev_qa"]))

    def test_candidate_confirmation_uses_editable_complete_question(self):
        ambiguous = failure("存在多个候选实体")
        ambiguous["intent"] = "Q_COMPANY_PATENTS"
        ambiguous["entities"]["candidates"] = [{"slot": "applicant", "id": "test-a", "name": "测试机构 A", "type": "Applicant", "score": .82},
                                                {"slot": "applicant", "id": "test-b", "name": "测试机构 B", "type": "Applicant", "score": .76}]
        app = open_workbench()
        with patch("qa.service.answer", return_value=ambiguous):
            app.chat_input[0].set_value("某机构有什么专利？").run()
        turn = app.session_state["ev_qa"]["turns"][-1]
        candidate = next(item for item in app.selectbox if item.key == f'ev_candidate_{turn["id"]}')
        candidate.select(1).run()
        self.assertFalse(app.exception)
        with patch("qa.service.answer", return_value=result("Q_COMPANY_PATENTS", ROWS["Q_COMPANY_PATENTS"])) as service:
            button(app, f'ev_confirm_{turn["id"]}').click().run()
            self.assertFalse(app.exception, app.exception)
            self.assertIn("测试机构 B", service.call_args.args[0])
            self.assertEqual(service.call_args.kwargs, {"mode": "auto"})
            self.assertEqual(len(app.session_state["ev_qa"]["turns"]), 2)


if __name__ == "__main__":
    unittest.main()
