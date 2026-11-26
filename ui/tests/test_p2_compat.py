"""P3-only contract, safe-template and navigation regressions."""
import unittest
from unittest.mock import patch
from qa import intents as I
from ui.questions import OPERATIONS, build_question, UnsupportedTemplate, split_compound
from ui.qa_status import response_status
from ui.qa_state import failure, normalize_answer
from ui.tests.test_workbench import open_workbench, button
from core import config


class TemplateTests(unittest.TestCase):
    def test_all_twelve_intents_and_exact_entities(self):
        self.assertEqual(len(OPERATIONS),12)
        for operation,(intent,_) in OPERATIONS.items():
            name="驱动电机" if I.ENTITY_SLOT.get(intent)=="topic" else "国家电网"
            question=build_question(operation,name)
            self.assertEqual(I.rule_intent(question),intent)
            slot=I.ENTITY_SLOT.get(intent)
            if slot:self.assertEqual(I.rule_slots(question,intent)[slot],name)

    def test_punctuation_years_and_unsupported_requests(self):
        name="Doowon Climate Control Co., Ltd."
        self.assertEqual(I.rule_slots(build_question("patents",name),I.PATENTS)["applicant"],name)
        self.assertEqual(I.rule_slots(build_question("trend","驱动电机",(2015,2023)),I.TREND)["end_year"],2023)
        for operation,name,years in [("patent_id","CN123",None),("patents","机构2020",None),
                                    ("patents","机构「子公司」",None),("trend","驱动电机",(2024,2025))]:
            with self.subTest(operation=operation,name=name),self.assertRaises(UnsupportedTemplate):
                build_question(operation,name,years)
        questions=split_compound("「国家电网」的技术布局和代表性专利有哪些？")
        self.assertEqual([I.rule_intent(q) for q in questions],[I.TOPICS,I.PATENTS])

    def test_compatible_statuses_and_unknown_neutral(self):
        for text,status in [("请提供创新主体","NEED_CLARIFICATION"),("暂不支持销量","OUT_OF_SCOPE"),
                            ("未查到证据","DATA_UNAVAILABLE"),("查询超时","SYSTEM_ERROR"),
                            ("其他未分类情况","UNCLASSIFIED")]:
            self.assertEqual(response_status(failure(text)),status)
        item=failure("候选");item["entities"]["candidates"]=[{"name":"A"}]
        self.assertEqual(response_status(item),"AMBIGUOUS_ENTITY")
        item=failure("兼容字段");item["status"]="DATA_UNAVAILABLE"
        self.assertEqual(response_status(normalize_answer(item)),"DATA_UNAVAILABLE")


class InteractionTests(unittest.TestCase):
    def setUp(self):
        for name,value in [("USE_SAMPLE",True),("QA_BACKEND","mock")]:
            setting=patch.object(config,name,value);setting.start();self.addCleanup(setting.stop)

    def test_compound_never_submits_until_single_explicit_action(self):
        app=open_workbench()
        with patch("qa.service.answer") as service:
            app.chat_input[0].set_value("「国家电网」的技术布局和代表性专利有哪些？").run()
            self.assertFalse(app.exception,app.exception)
            service.assert_not_called()
            self.assertEqual(len(app.session_state["ev_qa"]["compose_suggestions"]),2)
            button(app,"ev_split_1").click().run()
            self.assertFalse(app.exception,app.exception)
            service.assert_not_called()
            self.assertEqual(app.session_state["ev_qa"]["draft"],build_question("patents","国家电网"))

    def test_return_restores_whitelisted_source_without_request(self):
        from ui.navigation import OVERVIEW,QA
        app=open_workbench()
        app.switch_page(OVERVIEW).run()
        next(w for w in app.radio if w.key=="ov_dimension").set_value("公开国别").run()
        next(w for w in app.selectbox if w.key=="ov_topic").set_value("驱动电机").run()
        with patch("qa.service.answer") as service:
            button(app,"ov_topic_ask").click().run()
            app.switch_page(QA).run()
            self.assertFalse(app.exception,app.exception)
            service.assert_not_called()
            self.assertEqual(app.session_state["ev_qa"]["draft_origin"]["page"],OVERVIEW)
            button(app,"ev_return_source").click().run()
            app.switch_page(OVERVIEW).run()
            self.assertFalse(app.exception,app.exception)
            self.assertEqual(app.session_state["ov_topic"],"驱动电机")
            self.assertEqual(app.session_state["ov_dimension"],"公开国别")
            service.assert_not_called()

    def test_subject_return_preserves_selection_and_model_downgrade_notice(self):
        from ui.navigation import SUBJECTS,QA
        from ui.tests.test_models import result,ROWS
        app=open_workbench();app.switch_page(SUBJECTS).run()
        next(w for w in app.text_input if w.key=="org_query").set_value("国家电网").run()
        selected=app.session_state["org_selected"]
        with patch("qa.service.answer",return_value=result(rows=ROWS["Q_TOP_APPLICANTS"])) as service:
            button(app,"org_ask").click().run();app.switch_page(QA).run()
            service.assert_not_called()
            next(w for w in app.selectbox if w.key=="ev_qa_mode").set_value("llm").run()
            question=app.session_state["ev_qa"]["draft"]
            with patch.object(config,"QA_BACKEND","real"):
                app.chat_input[0].set_value(question).run()
            service.assert_called_once_with(question,mode="llm")
            self.assertFalse(app.exception,app.exception)
            self.assertTrue(any("本次实际使用规则模式" in str(item.value) for item in app.info))
            app.run();service.assert_called_once()
            button(app,"ev_return_source").click().run();app.switch_page(SUBJECTS).run()
            self.assertFalse(app.exception,app.exception)
            self.assertEqual(app.session_state["org_query"],"国家电网")
            self.assertEqual(app.session_state["org_selected"],selected)


if __name__=="__main__":unittest.main()
