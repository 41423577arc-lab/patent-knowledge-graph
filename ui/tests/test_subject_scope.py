"""Stage 01: real delivered scopes, plus explicit policy-conflict fixtures."""
import os
import unittest
from unittest.mock import patch

import pandas as pd

from core import config
from core.database import run_query
from qa import auxiliary
from qa.entity_linker import Catalog
from analysis import page_data as data
from analysis.subjects import build_index


class SubjectScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(config,"USE_SAMPLE",False): cls.bundle=data.dataset()
        cls.index=cls.bundle["subjects"]

    def test_current_delivery_is_verified_and_counts_match_p1(self):
        self.assertTrue(self.index["available"],self.index["note"])
        self.assertEqual(self.index["count_differences"],[])
        self.assertEqual(len(self.index["members"]),27190)
        self.assertEqual(len(self.index["raw_patents"]),27557)
        self.assertEqual(len(self.bundle["metrics"]),27557)
        self.assertEqual(len(self.bundle["topic_year"]),1293)
        self.assertEqual({n:len(ids) for n,ids in self.index["raw_patents"].items()},
                         self.bundle["metrics"].set_index("applicant_std")["patent_count"].to_dict())
        for metric in data.METRIC_LABELS:self.assertTrue(data.metric_available(self.bundle,metric))

    def test_p2_and_p3_have_identical_exact_member_sets(self):
        with patch.object(config,"USE_SAMPLE",False):
            aliases=auxiliary.aliases();catalog=Catalog("applicant",aliases)
        self.assertEqual(self.index["aliases"],aliases)
        self.assertEqual({n:frozenset(v) for n,v in catalog.members.items()},
                         {n:frozenset(v) for n,v in self.index["members"].items()})

    def test_alias_and_unmapped_subjects_use_unique_current_patents(self):
        index=self.index;witness=None
        for name,members in index["members"].items():
            if len(members)>1:
                summed=sum(len(index["raw_patents"][m]) for m in members)
                if summed>len(index["patents"][name]):witness=(name,members,summed);break
        self.assertIsNotNone(witness,"The delivered co-applicant aliases must provide a deduplication witness")
        name,members,summed=witness
        patents=data.patent_selection(self.bundle,applicant=name,merged=True)
        expected=set().union(*(index["raw_patents"][n] for n in members))
        self.assertEqual(set(patents["patent_id"]),expected)
        self.assertLess(len(patents),summed)
        alias=next(n for n in members if n!=name)
        self.assertIn(name,data.subject_names(self.bundle,alias,merged=True))
        plain=next(n for n,v in index["members"].items() if v==(n,) and n not in index["aliases"])
        self.assertEqual(data.subject_members(self.bundle,plain,merged=True),(plain,))
        self.assertEqual(index["patents"][plain],index["raw_patents"][plain])

    def test_pending_and_conflicting_aliases_are_not_merged(self):
        self.assertIn("中国南方",self.index["pending"])
        self.assertNotIn("中国南方",self.index["aliases"])
        self.assertEqual(self.index["members"]["中国南方"],("中国南方",))
        self.assertFalse(self.index["cooperation"][["app_a","app_b"]].eq("中国南方").any().any())
        # A mapping-policy fixture uses real names, never new business claims.
        names=list(self.index["raw_patents"])[:3];a,b,c=names
        frame=pd.DataFrame([(a,b,"manual"),(a,c,"auto_en"),(b,b,"pending_review")],columns=["alias","canonical","method"])
        with patch("qa.auxiliary._read",return_value=frame): approved=auxiliary.aliases()
        self.assertNotIn(a,approved)
        result=build_index(self.bundle["tables"],approved,frame,sample=True)
        self.assertIn(a,result["conflicts"])
        self.assertNotIn(a,result["aliases"])
        self.assertEqual(result["members"][b],(b,))

    def test_merged_edges_match_intersections_and_keep_p1_weights(self):
        for row in self.index["cooperation"].itertuples():
            self.assertNotEqual(row.app_a,row.app_b)
            self.assertEqual(row.weight,len(self.index["patents"][row.app_a]&self.index["patents"][row.app_b]))
        self.assertEqual(len(self.index["corrections"]),3)
        for item in self.index["corrections"]:
            self.assertGreater(item["p1_weight"],item["evidence_count"])
            actual=data.shared_patents(self.bundle,item["app_a"],item["app_b"],merged=True)
            self.assertEqual(len(actual),item["evidence_count"])
            self.assertTrue(item["raw_pairs"])

    def test_sample_never_loads_full_counts_or_cooperation(self):
        data._snapshot.clear()
        reader=pd.read_csv
        with patch.object(config,"USE_SAMPLE",True), \
             patch("qa.auxiliary.merged_cooperation",side_effect=AssertionError("full cooperation read in sample")), \
             patch("analysis.subjects.pd.read_csv",wraps=reader) as reads:
            sample=data.dataset()
            self.assertTrue(sample["subjects"]["available"],sample["subjects"]["note"])
            self.assertTrue(sample["subjects"]["sample"])
            self.assertEqual(sample["subjects"]["count_differences"],[])
            self.assertFalse(any(str(call.args[0]).endswith("company_patent_counts.csv") for call in reads.call_args_list))
            sample_ids=set(sample["tables"]["patents"]["patent_id"])
            for ids in sample["subjects"]["patents"].values():self.assertLessEqual(ids,sample_ids)
            for row in sample["subjects"]["cooperation"].itertuples():
                self.assertEqual(row.weight,len(sample["subjects"]["patents"][row.app_a]&sample["subjects"]["patents"][row.app_b]))

    def test_network_metrics_remain_original_and_never_sum(self):
        for metric in ["cited_count","pagerank","degree","betweenness"]:
            with self.assertRaises(ValueError):data.ranking(self.bundle,metric=metric,merged=True)
            ranked=data.ranking(self.bundle,metric=metric)
            original=self.bundle["metrics"].set_index("applicant_std")
            for row in ranked.to_dict("records"):
                self.assertEqual(row[metric],original.loc[row["applicant_std"],metric])


@unittest.skipUnless(os.getenv("P3_LIVE_FULL")=="1","Requires matching full P1 graph")
class LiveSubjectScopeTests(unittest.TestCase):
    def test_p2_resolved_members_query_same_patents_as_p3(self):
        with patch.object(config,"USE_SAMPLE",False):
            bundle=data.dataset();catalog=Catalog("applicant",auxiliary.aliases())
            for name in ["现代公司","国家电网","中国南方"]:
                entity,candidates=catalog.link(f"创新主体「{name}」的代表性专利有哪些？",mention=name,exact_only=True)
                self.assertIsNotNone(entity,(name,candidates))
                self.assertEqual(tuple(sorted(entity.members)),data.subject_members(bundle,name,merged=True))
                rows=run_query('MATCH (a:Applicant)-[:APPLIES_FOR]->(p:Patent) WHERE a.name IN $members RETURN DISTINCT p.patent_id AS id',{"members":list(entity.members)})
                self.assertEqual({row["id"] for row in rows},set(data.patent_selection(bundle,applicant=name,merged=True)["patent_id"]))


if __name__=="__main__":unittest.main()
