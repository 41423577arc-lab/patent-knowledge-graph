"""P3 integration checks using the delivered real sample, not invented business facts."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import config
from analysis import page_data as data
from streamlit.testing.v1 import AppTest


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        setting=patch.object(config,"USE_SAMPLE",True); setting.start(); self.addCleanup(setting.stop)
        self.bundle=data.dataset()

    def test_filters_share_one_scope_and_portfolios_match(self):
        patents=self.bundle["tables"]["patents"]
        year=int(patents["apply_year"].dropna().iloc[0])
        filtered=data.overview_data((year,year),bundle=self.bundle)
        self.assertEqual(set(filtered["patents"]["patent_id"]),set(patents.loc[patents["apply_year"].eq(year),"patent_id"]))
        self.assertTrue(set(filtered["topics"]["patent_id"])<=set(filtered["technical"]["patent_id"]))
        name=self.bundle["tables"]["applicants"]["applicant_std"].iloc[0]
        actual=data.patent_selection(self.bundle,applicant=name)
        expected=set(self.bundle["tables"]["applicants"].loc[lambda t:t["applicant_std"].eq(name),"patent_id"])
        self.assertEqual(set(actual["patent_id"]),expected & set(patents["patent_id"]))

    def test_cooperation_intersection_and_patent_search_pagination(self):
        applicants=self.bundle["tables"]["applicants"]
        links=self.bundle["tables"]["cooperation"]
        for row in links.head(10).itertuples():
            expected=set(applicants.loc[applicants["applicant_std"].eq(row.app_a),"patent_id"]) & set(applicants.loc[applicants["applicant_std"].eq(row.app_b),"patent_id"])
            self.assertEqual(set(data.shared_patents(self.bundle,row.app_a,row.app_b)["patent_id"]),expected & set(self.bundle["tables"]["patents"]["patent_id"]))
        patents=data.patent_selection(self.bundle)
        sample=patents.iloc[0]
        self.assertIn(sample.patent_id,set(data.patent_selection(self.bundle,query=sample.patent_id)["patent_id"]))
        first,_,_=data.page_slice(patents,1,10); second,_,_=data.page_slice(patents,2,10)
        self.assertTrue(set(first.patent_id).isdisjoint(set(second.patent_id)))
        self.assertEqual(data.patent_detail(self.bundle,sample.patent_id)["patent"]["title"],sample.title)

    def test_cache_hits_and_sample_full_isolation(self):
        data._snapshot.clear()
        original=data.load_table
        with patch("analysis.page_data.load_table",wraps=original) as loader:
            data.dataset(); data.dataset(); self.assertEqual(loader.call_count,7)
        with TemporaryDirectory() as directory, patch.object(config,"USE_SAMPLE",False), patch.object(config,"PROCESSED_DIR",Path(directory)):
            with self.assertRaises(FileNotFoundError): data.dataset()
        self.assertEqual(len(data.dataset()["tables"]["patents"]),len(self.bundle["tables"]["patents"]))

    def test_unavailable_metric_does_not_return_patent_count(self):
        bundle={**self.bundle,"metrics":None}
        frame=data.ranking(bundle,metric="pagerank")
        self.assertTrue(frame.empty)
        self.assertNotIn("patent_count",frame)

    def test_result_source_identity_rejects_same_size_changed_content(self):
        tables=self.bundle["tables"]
        candidate=data.topic_year().copy()
        manifest={"source_rows":{n:len(t) for n,t in tables.items()},
                  "source_table_sha256":{n:data.hashlib.sha256(t.to_json(orient="split",index=False,date_format="iso",force_ascii=False).encode("utf-8")).hexdigest() for n,t in tables.items()}}
        candidate.attrs["metrics_manifest"]=manifest
        def result(name):
            if name=="topic_year": return candidate
            raise FileNotFoundError(name)
        with patch("analysis.page_data.load_result",side_effect=result):
            data._snapshot.clear()
            self.assertIsNotNone(data.dataset()["topic_year"])
            manifest["source_table_sha256"]["patents"]="changed-content-same-row-count"
            data._snapshot.clear()
            stale=data.dataset()
            self.assertIsNone(stale["topic_year"])
            self.assertIn("来源内容",stale["result_notes"]["topic_year"])
        data._snapshot.clear()


class PageFlowTests(unittest.TestCase):
    def setUp(self):
        for name,value in [("USE_SAMPLE",True),("QA_BACKEND","mock")]:
            p=patch.object(config,name,value);p.start();self.addCleanup(p.stop)

    def test_reset_and_cross_page_prefill_never_submits(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[2]/"app.py"),default_timeout=60).run()
        app.switch_page("pages/01_产业技术全景.py").run();self.assertFalse(app.exception,app.exception)
        patents=data.dataset()["tables"]["patents"]
        self.assertEqual(next(w for w in app.metric if w.label=="全部专利").value,str(int(patents["is_in_sample"].sum())))
        countries=next(w for w in app.multiselect if w.key=="ov_countries")
        if countries.options:
            countries.select(countries.options[0]).run()
            next(b for b in app.button if b.label=="重置筛选").click().run()
            self.assertEqual(app.session_state["ov_countries"],[])
        app.switch_page("pages/02_创新主体与合作网络.py").run();self.assertFalse(app.exception,app.exception)
        with patch("qa.service.answer") as service:
            next(b for b in app.button if b.key=="org_ask").click().run()
            self.assertFalse(app.exception,app.exception)
            self.assertEqual(len(app.chat_input),1)
            self.assertEqual(app.session_state["ev_qa"]["turns"],[])
            self.assertIn("创新主体",app.session_state["ev_qa"]["draft"])
            service.assert_not_called()


if __name__=="__main__":unittest.main()
