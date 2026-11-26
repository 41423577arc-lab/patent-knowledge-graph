"""Discovery filters and explicit handoffs through the unchanged P2 service."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from core import config
from analysis import page_data as data
from ui.evidence import subject_question
from qa import intents

APP=str(Path(__file__).resolve().parents[2]/"app.py")


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        for name,value in [("USE_SAMPLE",True),("QA_BACKEND","mock")]:
            p=patch.object(config,name,value);p.start();self.addCleanup(p.stop)
        self.bundle=data.dataset()

    def test_generated_subject_questions_have_one_supported_intent(self):
        for kind,intent in [("topics",intents.TOPICS),("patents",intents.PATENTS),("cooperation",intents.COOP)]:
            question=subject_question("国家电网",kind)
            self.assertEqual(intents.rule_intent(question),intent)
            self.assertEqual(question.count("「"),1)

    def test_topic_history_matches_filtered_patent_sets(self):
        topics=self.bundle["tables"]["patent_topic"]["topic"].dropna().unique()[:3]
        country=self.bundle["tables"]["patents"]["country"].dropna().iloc[0]
        for countries in [None,[country]]:
            scope=data.overview_data((2015,2023),countries,bundle=self.bundle)
            for topic in topics:
                rows,_=data.topic_history(self.bundle,scope,topic,(2015,2023),countries)
                ids=scope["topics"].loc[scope["topics"]["topic"].eq(topic),"patent_id"]
                expected=scope["technical"].loc[lambda t:t["patent_id"].isin(ids)].groupby("apply_year")["patent_id"].nunique()
                self.assertEqual(dict(zip(rows["year"],rows["count"])),expected.to_dict())
        rows,_=data.topic_history(self.bundle,scope,topics[0],(2024,2025),countries)
        self.assertTrue(rows.empty)

    def test_patent_prefill_keeps_context_without_submitting(self):
        app=AppTest.from_file(APP,default_timeout=90).run()
        app.switch_page("pages/01_产业技术全景.py").run()
        self.assertFalse(app.exception,app.exception)
        with patch("qa.service.answer") as service:
            next(b for b in app.button if b.key=="ov_patents_ask").click().run()
            self.assertFalse(app.exception,app.exception)
            self.assertIn("来自专利",app.session_state["ev_qa"]["draft_context"])
            self.assertEqual(intents.rule_intent(app.session_state["ev_qa"]["draft"]),intents.PATENTS)
            service.assert_not_called()
        next(b for b in app.button if b.key=="ev_qa_new").click().run()
        self.assertIsNone(app.session_state["ev_qa"]["draft_context"])


@unittest.skipUnless(os.getenv("P3_LIVE_FULL")=="1","Set P3_LIVE_FULL=1 for the matching full P1 database")
class LiveDiscoveryTests(unittest.TestCase):
    def test_subject_to_real_answer_and_history_source(self):
        with patch.object(config,"USE_SAMPLE",False),patch.object(config,"QA_BACKEND","real"):
            app=AppTest.from_file(APP,default_timeout=120).run()
            app.switch_page("pages/02_创新主体与合作网络.py").run()
            self.assertFalse(app.exception,app.exception)
            next(w for w in app.text_input if w.key=="org_query").set_value("国家电网").run()
            next(w for w in app.selectbox if w.key=="org_selected").select("国家电网").run()
            next(w for w in app.selectbox if w.key=="org_qa_action").select("patents").run()
            next(b for b in app.button if b.key=="org_ask").click().run()
            self.assertEqual(app.session_state["ev_qa"]["turns"],[])
            # AppTest must retain the destination hash for subsequent widget reruns.
            app.switch_page("pages/03_智能问答与关联路径.py").run()
            next(w for w in app.selectbox if w.key=="ev_qa_mode").select("rule").run()
            self.assertFalse(app.exception,app.exception)
            question=app.session_state["ev_qa"]["draft"]
            app.chat_input[0].set_value(question).run()
            self.assertFalse(app.exception,app.exception)
            turn=app.session_state["ev_qa"]["turns"][-1]
            self.assertTrue(turn["answer"]["ok"],turn["answer"]["error"])
            self.assertEqual(turn["answer"]["intent"],intents.PATENTS)
            self.assertIn("国家电网",turn["source_context"])
            self.assertTrue(turn["answer"]["data"])
            self.assertTrue(turn["answer"]["graph"]["edges"])


if __name__=="__main__":unittest.main()
