"""Filtered aggregates, restricted exports and actual native page interactions."""
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
from core import config
from analysis import page_data as data
from ui.exports import summary_csv
from ui.selection import selected_rank_name
from ui.navigation import OVERVIEW,SUBJECTS,QA
from ui.tests.test_workbench import open_workbench,button


class AggregateTests(unittest.TestCase):
    def test_multi_domain_topic_filter_and_dedup(self):
        patents=pd.DataFrame([{"patent_id":"p1","is_in_sample":True,"apply_year":2020,"patent_type":"发明"},
                              {"patent_id":"p2","is_in_sample":True,"apply_year":2024,"patent_type":"发明"}])
        tables={"patents":patents,"applicants":pd.DataFrame({"patent_id":["p1","p1","p2"],"applicant_std":["A","A","B"]}),
                "patent_topic":pd.DataFrame({"patent_id":["p1","p1","p1","p2"],"topic":["T1","T1","T2","T1"],"domain":["D1","D1","D2","D1"]}),
                "patent_ipc":pd.DataFrame({"patent_id":[],"ipc_code":[]}),"patent_efficacy":pd.DataFrame({"patent_id":[]})}
        bundle={"tables":tables,"topic_year":None}
        scope=data.overview_data(domain=["D1"],bundle=bundle)
        self.assertEqual(set(scope["topics"]["topic"]),{"T1"})
        history,note=data.topic_history(bundle,scope,"T1",domains=["D1"])
        self.assertEqual(history.to_dict("records"),[{"year":2020,"count":1}])
        self.assertIn("申请年",note)
        owners=data.topic_subjects(bundle,scope,"T1")
        self.assertEqual(owners.set_index("applicant_std")["patent_count"].to_dict(),{"A":1,"B":1})

    def test_summary_exports_roundtrip_context_and_block_raw_fields(self):
        frame=pd.DataFrame({"topic":["驱动电机"],"year":[2020],"count":[3]})
        exported=pd.read_csv(io.BytesIO(summary_csv(frame,"申请年；公开国别=CN")))
        self.assertEqual(exported["count"].tolist(),[3]);self.assertIn("公开国别=CN",exported["统计范围"].iloc[0])
        for field in ["abstract","patent_id","title"]:
            with self.assertRaises(ValueError):summary_csv(pd.DataFrame({field:["raw"]}),"范围")

    def test_topic_and_domain_must_match_same_association(self):
        scope={"patents":pd.DataFrame({"patent_id":["A","B"]}),
               "topics":pd.DataFrame({"patent_id":["A","B"],"topic":["T1","T2"],"domain":["D1","D1"]})}
        # B may have T1 in a different domain in the underlying raw table; it must stay excluded.
        self.assertEqual(data.topic_patents(scope,"T1")["patent_id"].tolist(),["A"])
        self.assertEqual(data.topic_patents(scope,None)["patent_id"].tolist(),["A","B"])

    def test_rank_selection_only_uses_current_records(self):
        event={"selection":{"points":[{"customdata":["A"]}]}}
        self.assertEqual(selected_rank_name(event,["A","B"]),"A")
        self.assertIsNone(selected_rank_name(event,["B"]))
        self.assertIsNone(selected_rank_name({"selection":{"points":[{"x":"A"}]}},["A"]))


class PageTests(unittest.TestCase):
    def setUp(self):
        for name,value in [("USE_SAMPLE",True),("QA_BACKEND","mock")]:
            p=patch.object(config,name,value);p.start();self.addCleanup(p.stop)

    def test_real_country_option_has_nonempty_matching_summary(self):
        bundle=data.dataset()
        country=bundle["tables"]["patents"].country.value_counts().index[0]
        expected=data.overview_data(country=[country],bundle=bundle)
        self.assertGreater(expected["patent_count"],0)
        app=open_workbench();app.switch_page(OVERVIEW).run()
        control=next(w for w in app.multiselect if w.key=="ov_countries")
        self.assertIn(country,control.options)
        control.set_value([country]).run()
        self.assertFalse(app.exception,app.exception)
        metric=next(w for w in app.metric if w.label=="全部专利")
        self.assertEqual(metric.value,f'{expected["patent_count"]:,}')
        self.assertEqual(app.session_state["ov_countries"],[country])

    def test_search_topic_subject_handoff_and_return_reset(self):
        app=open_workbench();app.switch_page(OVERVIEW).run()
        next(w for w in app.text_input if w.key=="ov_topic_query").set_value("驱动").run()
        next(w for w in app.selectbox if w.key=="ov_topic").set_value("驱动电机").run()
        subject=app.session_state["ov_topic_subject"]
        with patch("qa.service.answer") as service:
            button(app,"ov_open_subject").click().run();app.switch_page(SUBJECTS).run()
            self.assertFalse(app.exception,app.exception)
            self.assertEqual(app.session_state["org_selected"],subject)
            button(app,"org_return_overview").click().run();app.switch_page(OVERVIEW).run()
            self.assertEqual(app.session_state["ov_topic_query"],"驱动")
            self.assertEqual(app.session_state["ov_topic"],"驱动电机")
            service.assert_not_called()
        button(app,"ov_reset").click().run()
        self.assertFalse(app.exception,app.exception)
        self.assertEqual(app.session_state["ov_topic_query"],"");self.assertIsNone(app.session_state["ov_topic"])

    def test_rank_plot_retargets_profile_and_patent_view(self):
        import streamlit as st
        bundle=data.dataset();names=data.ranking(bundle,top_n=10,merged=True)["applicant_std"].tolist()
        picked=names[2];original=st.plotly_chart
        def render(*args,**kwargs):
            actual=original(*args,**kwargs)
            return {"selection":{"points":[{"customdata":[picked]}]}} if kwargs.get("key","").startswith("org_rank_plot_") else actual
        app=open_workbench()
        with patch("streamlit.plotly_chart",side_effect=render):app.switch_page(SUBJECTS).run()
        self.assertFalse(app.exception,app.exception);self.assertEqual(app.session_state["org_selected"],picked)
        next(w for w in app.radio if w.key=="org_evidence_view").set_value("全部关联专利").run()
        self.assertFalse(app.exception,app.exception)
        self.assertEqual(app.session_state["org_selected"],picked)

    def test_table_and_cooperation_edge_node_selection(self):
        import streamlit as st
        app=open_workbench();bundle=data.dataset()
        names=data.ranking(bundle,top_n=10,merged=True)["applicant_std"].tolist()
        selected=names[1];original_table=st.dataframe
        def table(*args,**kwargs):
            actual=original_table(*args,**kwargs)
            return SimpleNamespace(selection=SimpleNamespace(rows=[1])) if kwargs.get("key")=="org_rank_table" else actual
        with patch("streamlit.dataframe",side_effect=table):app.switch_page(SUBJECTS).run()
        self.assertFalse(app.exception,app.exception);self.assertEqual(app.session_state["org_selected"],selected)
        # Pick a connected subject from actual current scope, not an invented relationship.
        edge=bundle["subjects"]["cooperation"].iloc[0]
        next(w for w in app.text_input if w.key=="org_query").set_value(edge.app_a).run()
        next(w for w in app.selectbox if w.key=="org_selected").set_value(edge.app_a).run()
        links=data.cooperation_for(edge.app_a,bundle,merged=True)
        index=len(links)-1;chosen=links.iloc[index]
        partner=chosen.app_b if chosen.app_a==edge.app_a else chosen.app_a
        original_plot=st.plotly_chart
        def plot(custom):
            def render(*args,**kwargs):
                actual=original_plot(*args,**kwargs)
                return SimpleNamespace(selection=SimpleNamespace(points=[{"customdata":custom}])) if kwargs.get("key")=="org_network" else actual
            return render
        with patch("streamlit.plotly_chart",side_effect=plot(["edge",str(index)])):app.run()
        self.assertFalse(app.exception,app.exception);self.assertEqual(app.session_state["org_partner"],partner)
        with patch("streamlit.plotly_chart",side_effect=plot(["node",partner])):app.run()
        self.assertFalse(app.exception,app.exception);self.assertEqual(app.session_state["org_selected"],partner)


@unittest.skipUnless(os.getenv("P3_LIVE_FULL")=="1","Requires fixed full P1 data")
class LiveAggregateTests(unittest.TestCase):
    def test_qa_exact_patent_location_never_resends_question(self):
        from qa.service import answer
        from ui.questions import build_question
        with patch.object(config,"USE_SAMPLE",False),patch.object(config,"QA_BACKEND","real"):
            question=build_question("patents","国家电网");response=answer(question,mode="rule")
            self.assertTrue(response["ok"],response["error"])
            node=next(n for n in response["graph"]["nodes"] if n["type"]=="Patent")
            app=open_workbench()
            with patch("qa.service.answer",return_value=response) as service:
                app.chat_input[0].set_value(question).run()
                turn=app.session_state["ev_qa"]["turns"][-1]
                next(w for w in app.selectbox if w.key==f'ev_inspect_{turn["id"]}').set_value(("node",node["id"])).run()
                button(app,f'ev_locate_{turn["id"]}_{node["id"]}').click().run()
                self.assertFalse(app.exception,app.exception)
                service.assert_called_once()
                self.assertTrue(any(node["label"] in str(w.value) for w in app.markdown))

    def test_full_and_sample_precompute_filters_representatives_and_cooperation(self):
        for sample in [True,False]:
            with patch.object(config,"USE_SAMPLE",sample):
                bundle=data.dataset();self.assertIsNotNone(bundle["topic_year"])
                self.assertEqual(bundle["topic_year"].attrs["scope"],"sample" if sample else "full")
                window=data.overview_data((2015,2023),bundle=bundle)
                country=window["patents"]["country"].value_counts().index[0]
                domain=window["topics"]["domain"].dropna().iloc[0]
                for countries,domains in [(None,None),([country],None),(None,[domain])]:
                    scope=data.overview_data((2015,2023),countries,domains,bundle)
                    self.assertGreater(len(scope["patents"]),0)
                    if countries:self.assertEqual(set(scope["patents"].country),set(countries))
                    topics=list(scope["topics"]["topic"].unique())[:3]
                    self.assertTrue(topics)
                    for topic in topics:
                        rows,note=data.topic_history(bundle,scope,topic,(2015,2023),countries,domains)
                        ids=set(scope["topics"].loc[scope["topics"]["topic"].eq(topic),"patent_id"])
                        expected=scope["technical"].loc[lambda t:t["patent_id"].isin(ids)].groupby("apply_year")["patent_id"].nunique().to_dict()
                        self.assertEqual(dict(zip(rows.year,rows["count"])),expected)
                        owners=data.topic_subjects(bundle,scope,topic,merged=True)
                        for row in owners.itertuples():
                            actual=set(bundle["subjects"]["patents"][row.applicant_std])&ids
                            self.assertEqual(row.patent_count,len(actual))
                patents=data.patent_selection(bundle,applicant="国家电网",merged=True)
                chosen=data.representative_patents(bundle,patents)
                self.assertLessEqual(len(chosen),10)
                self.assertLessEqual(set(chosen.patent_id),set(patents.patent_id))
                for row in chosen.itertuples():self.assertEqual(row.cited_count,data.patent_citation_stats(bundle,row.patent_id)["cited_count"])
                summary=data.cooperation_summary(bundle,"现代公司",merged=True)
                for row in summary.itertuples():
                    self.assertEqual(row.shared_count,len(data.shared_patents(bundle,row.app_a,row.app_b,merged=True)))
                    self.assertEqual(row.weight,row.shared_count)


if __name__=="__main__":unittest.main()
