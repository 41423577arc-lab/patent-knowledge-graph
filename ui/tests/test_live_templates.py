"""Opt-in P3 templates against the fixed full P1 graph; only read queries."""
import json
import os
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
from core import config
from core.database import run_query
from core.data_loader import load_table
from qa import auxiliary
from qa import intents as I
from qa.service import answer
from qa.evidence_graph import EvidenceGraph
from qa.llm_client import ModelUnavailable
from ui.questions import OPERATIONS,build_question
from ui.qa_state import FIELDS,normalize_answer
from ui.qa_status import response_status

KEYS={"Applicant":"name","Patent":"patent_id","IPC":"code","Technology":"name","Domain":"name"}


@unittest.skipUnless(os.getenv("P3_LIVE_FULL")=="1","Set P3_LIVE_FULL=1 for the fixed full P1 graph")
class LiveTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        aliases=auxiliary.aliases();external=auxiliary.external_applicants()
        cites=load_table("citations")
        cls.external_cites=set(cites.loc[~cites.cited_in_sample.fillna(False),["citing_id","cited_id"]].itertuples(index=False,name=None))
        cls.external_owners={(aliases.get(row.applicant,row.applicant),row.cited_id) for row in external.itertuples()}

    def check_evidence(self,result):
        nodes={n["id"]:n for n in result["graph"]["nodes"]}
        grouped=defaultdict(list)
        for edge in result["graph"]["edges"]:
            self.assertTrue({edge["source"],edge["target"]}<=nodes.keys())
            self.assertGreaterEqual(edge["weight"],0)
            a,b=nodes[edge["source"]],nodes[edge["target"]]
            kind=edge["type"];self.assertIn(kind,EvidenceGraph.ENDPOINTS)
            self.assertEqual((a["type"],b["type"]),EvidenceGraph.ENDPOINTS[kind])
            grouped[kind].append({"a":a["label"],"b":b["label"]})
        for kind,edges in grouped.items():
            left,right=EvidenceGraph.ENDPOINTS[kind]
            direction="-" if kind=="CO_APPLIED_WITH" else "->"
            query=(f"UNWIND $edges AS e OPTIONAL MATCH (a:{left} {{{KEYS[left]}:e.a}})"
                   f"-[r:{kind}]{direction}(b:{right} {{{KEYS[right]}:e.b}}) RETURN e.a AS a,e.b AS b,count(r) AS count")
            for row in run_query(query,{"edges":edges}):
                if row["count"]:continue
                pair=(row["a"],row["b"])
                if kind=="CITES":self.assertIn(pair,self.external_cites)
                elif kind=="APPLIES_FOR":self.assertIn(pair,self.external_owners)
                else:self.fail(f"Unwitnessed {kind}: {pair}")

    def test_all_generated_templates_and_real_evidence(self):
        self.assertFalse(config.USE_SAMPLE);self.assertEqual(config.QA_BACKEND,"real")
        rows=[]
        for operation,(intent,_) in OPERATIONS.items():
            with self.subTest(operation=operation):
                name="驱动电机" if I.ENTITY_SLOT.get(intent)=="topic" else "国家电网"
                question=build_question(operation,name)
                result=answer(question,mode="rule")
                self.assertTrue(result["ok"],result["error"])
                self.assertEqual(result["intent"],intent)
                self.assertEqual(result["mode"],"rule")
                self.assertTrue(FIELDS<=result.keys());self.assertTrue(normalize_answer(result)["ok"])
                self.assertTrue(result["data"])
                slot=I.ENTITY_SLOT.get(intent)
                if slot:self.assertEqual(result["entities"]["resolved"][slot]["name"],name)
                json.dumps(result,ensure_ascii=False,allow_nan=False)
                self.check_evidence(result)
                rows.append({"operation":operation,"question":question,"intent":intent,"rows":len(result["data"]),
                             "nodes":len(result["graph"]["nodes"]),"edges":len(result["graph"]["edges"]),"status":"PASS"})
        folder=Path("tmp/integration-stage02");folder.mkdir(parents=True,exist_ok=True)
        (folder/"live-templates.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")

    def test_model_downgrade_retains_real_rule_result(self):
        with patch("qa.llm_client.classify",side_effect=ModelUnavailable("injected unavailable")),patch("qa.llm_client.organize",side_effect=ModelUnavailable("injected unavailable")):
            result=answer(build_question("patents","国家电网"),mode="llm")
        self.assertTrue(result["ok"],result["error"]);self.assertEqual(result["mode"],"rule")
        self.assertTrue(result["data"]);self.check_evidence(result)

    def test_actual_alias_punctuation_year_window_and_empty_result(self):
        for name in ["现代公司","Doowon Climate Control Co., Ltd."]:
            result=answer(build_question("patents",name),mode="rule")
            self.assertTrue(result["ok"],result["error"]);self.check_evidence(result)
        result=answer(build_question("trend","驱动电机",(2015,2023)),mode="rule")
        self.assertTrue(result["ok"],result["error"])
        self.assertEqual([r["year"] for r in result["data"]],list(range(2015,2024)))
        result=answer(build_question("patents","国家电网",(1900,1901)),mode="rule")
        self.assertEqual(response_status(normalize_answer(result)),"DATA_UNAVAILABLE")


if __name__=="__main__":unittest.main()
