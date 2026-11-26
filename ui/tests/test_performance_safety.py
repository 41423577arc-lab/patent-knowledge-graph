"""Performance changes must preserve filtering, isolation, provenance and errors."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from core import config
from analysis.membership import member_of
from analysis import page_data as data
from ui.navigation import OVERVIEW,SUBJECTS,QA
from ui.qa_state import failure
from ui.qa_visuals import graph_figure,validated_graph
from ui.tests.test_workbench import open_workbench


class FilteringTests(unittest.TestCase):
    def test_source_digest_preserves_original_serialization_and_rejects_changes(self):
        frame=pd.DataFrame({"id":pd.Series(["A",None,"B"],dtype="string[pyarrow]"),
                            "number":pd.Series([1,None,3],dtype="Int64"),"flag":[True,False,None]})
        options={"orient":"split","index":False,"date_format":"iso","force_ascii":False}
        expected=hashlib.sha256(frame.to_json(**options).encode()).hexdigest()
        self.assertEqual(data._source_digest(frame,expected),expected)
        # If an alternate object serialization differs, fall back to the original hash contract.
        with patch.object(frame,"astype") as alternate:
            alternate.return_value.to_json.return_value="different serialization"
            self.assertEqual(data._source_digest(frame,expected),expected)
        frame.loc[0,"id"]="changed"
        self.assertNotEqual(data._source_digest(frame,expected),expected)

    def test_membership_matches_pandas_with_nulls_duplicates_and_mixed_candidates(self):
        for dtype in [object,"string[python]","string[pyarrow]"]:
            series=pd.Series(["A","B",None,"A","",pd.NA],dtype=dtype)
            for values in [[],["A"],["A","A",None],[pd.NA],["",None],{"B"},["A",1]]:
                with self.subTest(dtype=dtype,values=values):
                    np.testing.assert_array_equal(member_of(series,values),series.isin(values))

    def test_cache_key_distinguishes_mode_path_file_and_manifest_content(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);results=root/"results";results.mkdir()
            manifest=results/"metrics_manifest.json";manifest.write_text('{"v":1}')
            with patch.object(config,"DATA_DIR",root),patch.object(config,"PROCESSED_DIR",root/"processed"),patch.object(config,"RESULTS_DIR",results),patch.object(config,"USE_SAMPLE",False):
                first=data.data_token();stat=manifest.stat()
                manifest.write_text('{"v":2}');os.utime(manifest,ns=(stat.st_atime_ns,stat.st_mtime_ns))
                self.assertNotEqual(first,data.data_token())
                full=data.data_token()
                with patch.object(config,"USE_SAMPLE",True):self.assertNotEqual(full,data.data_token())
                with patch.object(config,"DATA_DIR",root/"other"),patch.object(config,"PROCESSED_DIR",root/"other"/"processed"),patch.object(config,"RESULTS_DIR",root/"other"/"results"):
                    self.assertNotEqual(full,data.data_token())

    def test_graph_drawing_is_bounded_without_mutating_evidence_or_edge_indices(self):
        nodes=[{"id":f"Patent:P{i}","label":f"P{i}","type":"Patent"} for i in range(155)]
        edges=[{"source":nodes[i%154]["id"],"target":nodes[(i%154)+1]["id"],"type":"CITES","weight":1} for i in range(269)]
        # Include an early edge whose endpoint is excluded, making display indices non-contiguous.
        edges.insert(0,{"source":nodes[154]["id"],"target":nodes[0]["id"],"type":"CITES","weight":1})
        graph={"nodes":nodes,"edges":edges};original=deepcopy(graph)
        figure,notes=graph_figure(graph)
        self.assertTrue(any("完整证据" in n for n in notes))
        node_ids=set();edge_indices=[]
        for trace in figure.data:
            for meta in trace.customdata if trace.customdata is not None else []:
                if meta[0]=="node":node_ids.add(meta[1])
                elif meta[0]=="edge":
                    edge_indices.append(int(meta[1]));self.assertEqual((meta[2],meta[3]),(edges[int(meta[1])]["source"],edges[int(meta[1])]["target"]))
        self.assertLessEqual(len(node_ids),128);self.assertLessEqual(len(edge_indices),200)
        self.assertEqual(graph,original);self.assertEqual(len(validated_graph(graph)[1]),270)


class CacheAndFailureTests(unittest.TestCase):
    def setUp(self):
        for name,value in [("USE_SAMPLE",True),("QA_BACKEND","mock")]:
            setting=patch.object(config,name,value);setting.start();self.addCleanup(setting.stop)

    def test_shared_snapshot_views_do_not_leak_mutations(self):
        first=data.dataset();second=data.dataset()
        original=second["tables"]["patents"].iloc[0].title
        first["tables"]["patents"].iloc[0,first["tables"]["patents"].columns.get_loc("title")]="LOCAL-MUTATION"
        self.assertEqual(second["tables"]["patents"].iloc[0].title,original)
        name=next(iter(first["subjects"]["members"]))
        first["subjects"]["members"][name]=("LOCAL",)
        self.assertNotEqual(data.dataset()["subjects"]["members"][name],("LOCAL",))
        first["subjects"]["pending"].add("LOCAL-PENDING")
        self.assertNotIn("LOCAL-PENDING",data.dataset()["subjects"]["pending"])
        if data._cow_available():
            self.assertIsNot(first["tables"]["patents"],second["tables"]["patents"])
            a=first["tables"]["patents"]["patent_id"].array.__arrow_array__().chunk(0)
            b=second["tables"]["patents"]["patent_id"].array.__arrow_array__().chunk(0)
            self.assertEqual(a.buffers()[2].address,b.buffers()[2].address)
        first["metrics"].attrs["metrics_manifest"]["scope"]="LOCAL-MUTATION"
        self.assertEqual(second["metrics"].attrs["metrics_manifest"]["scope"],"sample")

    def test_older_pandas_path_keeps_independent_cached_copies(self):
        with patch.object(data,"_cow_available",return_value=False):
            first=data.dataset();second=data.dataset()
            title=second["tables"]["patents"].iloc[0].title
            first["tables"]["patents"].iloc[0,first["tables"]["patents"].columns.get_loc("title")]="LOCAL"
            self.assertEqual(data.dataset()["tables"]["patents"].iloc[0].title,title)

    def test_missing_tables_permission_and_schema_errors_keep_navigation_usable(self):
        app=open_workbench()
        for path in [OVERVIEW,SUBJECTS]:
            for error in [FileNotFoundError("private-secret"),PermissionError("private-secret"),ValueError("private-secret")]:
                with self.subTest(page=path,error=type(error).__name__),patch.object(data,"dataset",side_effect=error):
                    app.switch_page(path).run()
                    self.assertFalse(app.exception,app.exception);self.assertTrue(app.error)
                    self.assertNotIn("private-secret",str([e.value for e in app.error]))
                    self.assertTrue(any(b.key=="ev_retry_data" for b in app.button))
        app.switch_page(QA).run();self.assertFalse(app.exception,app.exception)

    def test_rejected_metric_is_not_served_and_missing_data_is_not_cached(self):
        data._snapshot.clear()
        with patch.object(data,"load_result",side_effect=ValueError("预计算来源内容与当前七表不一致")):
            bundle=data.dataset()
        self.assertIsNone(bundle["metrics"]);self.assertIsNone(bundle["topic_year"])
        self.assertIn("不一致",bundle["metric_note"])
        # A transient rejected metric must be retried, rather than negative-cached for ten minutes.
        self.assertIsNotNone(data.dataset()["metrics"])
        data._snapshot.clear()
        with patch.object(data,"load_table",side_effect=FileNotFoundError("injected")):
            with self.assertRaises(FileNotFoundError):data.dataset()
        self.assertEqual(len(data.dataset()["tables"]["patents"]),481)

    def test_disconnect_and_timeout_keep_question_retry_and_sources(self):
        app=open_workbench()
        for error in [ConnectionError("private-secret"),TimeoutError("private-secret")]:
            with patch("qa.service.answer",side_effect=error):
                app.chat_input[0].set_value("创新主体「国家电网」的代表性专利有哪些？").run()
            self.assertFalse(app.exception,app.exception)
            turn=app.session_state["ev_qa"]["turns"][-1]
            self.assertFalse(turn["answer"]["ok"]);self.assertEqual(turn["question"],"创新主体「国家电网」的代表性专利有哪些？")
            self.assertNotIn("private-secret",str(turn))
            self.assertTrue(any(b.key==f'ev_retry_{turn["id"]}' for b in app.button))

    def test_real_p2_disconnect_and_timeout_responses_are_displayed_as_failures(self):
        from qa.service import answer
        app=open_workbench()
        next(w for w in app.selectbox if w.key=="ev_qa_mode").set_value("rule").run()
        with patch.object(config,"QA_BACKEND","real"):
            for healthy in [False,True]:
                with patch("qa.retrieval.health_check",return_value=healthy),patch("qa.retrieval.run_query",side_effect=TimeoutError("private-secret")) as query,patch("qa.service.answer",wraps=answer) as service:
                    app.chat_input[0].set_value("创新主体「国家电网」的代表性专利有哪些？").run()
                    self.assertFalse(app.exception,app.exception)
                    service.assert_called_once()
                    if not healthy:query.assert_not_called()
                    turn=app.session_state["ev_qa"]["turns"][-1]
                    self.assertFalse(turn["answer"]["ok"]);self.assertTrue(app.error)
                    self.assertNotIn("private-secret",str(turn))

    def test_local_evidence_permission_failure_preserves_qa_result(self):
        from ui.tests.test_models import result
        from ui.tests.test_workbench import button
        graph={"nodes":[{"id":"Patent:INJECTED","label":"INJECTED","type":"Patent"}],"edges":[]}
        response=result("Q_COMPANY_PATENTS",[{"patent_id":"INJECTED"}],graph)
        app=open_workbench()
        with patch.object(config,"QA_BACKEND","real"),patch("qa.service.answer",return_value=response) as service:
            app.chat_input[0].set_value("测试本地证据读取失败").run()
            turn=app.session_state["ev_qa"]["turns"][-1]
            next(w for w in app.selectbox if w.key==f'ev_inspect_{turn["id"]}').set_value(("node","Patent:INJECTED")).run()
            with patch("ui.evidence.locate_patent",side_effect=PermissionError("private-secret")):
                button(app,f'ev_locate_{turn["id"]}_Patent:INJECTED').click().run()
            self.assertFalse(app.exception,app.exception);service.assert_called_once()
            self.assertTrue(any("本地证据暂不可读" in str(item.value) for item in app.info))
            self.assertEqual(app.session_state["ev_qa"]["turns"][-1]["answer"],response)


if __name__=="__main__":unittest.main()
