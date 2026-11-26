"""Network-free routing and evidence checks for the web supplement."""

import copy
import os
import unittest
from datetime import date
from unittest.mock import patch

import httpx

from core import config
from qa import answer_builder, intents, web_search
from qa.retrieval import QueryUnavailable, ScopeMismatch
from qa.service import answer

PUBLIC = (
    "2026年新能源汽车行业有哪些最新政策？",
    "比亚迪近期发布了哪些新能源汽车技术？",
    "2026年固态电池产业化有哪些新进展？",
    "当前新能源汽车行业有哪些重要技术趋势？",
    "最近公布的新能源汽车销量统计是什么？",
)
URL = "https://www.gov.cn/zhengce/test-fixture"


def response_payload():
    content = "这里是测试用已引用句。这里是未引用的数字123。"
    return {"choices": [{"finish_reason": "stop", "message": {
        "content": content, "server_tool_calls": [{"calls": [
            {"type": "deepseek_web_search", "kind": "search", "status": "completed",
             "sources": [{"url": URL, "published_at": "2025-12-31T16:00:00Z", "title": "测试来源"}]}]}],
        "annotations": [{"type": "url_citation", "url_citation": {
            "url": URL, "start_index": 0, "end_index": content.index("。") + 1}}]}}],
        "usage": {"server_tool_use": {"tool_search": 3}, "total_tokens": 120}}


class WebRoutingTests(unittest.TestCase):
    def setUp(self):
        flags = patch.dict(os.environ, QA_WEB_SEARCH_ENABLED="true")
        backend = patch.object(config, "QA_BACKEND", "real")
        for context in (flags, backend):
            context.start()
            self.addCleanup(context.stop)

    def test_kg_questions_keep_priority(self):
        cases = [intents.EXAMPLES[intent] for intent in (intents.TOP, intents.INFLUENCE, intents.GROWTH)]
        cases += ["「驱动电机」的年度申请量如何变化？", "本知识图谱中新能源汽车专利最多的是谁？",
                  "「驱动电机」的年度申请量如何变化，和政策有关吗？"]
        for question in cases:
            with self.subTest(question=question), patch.object(web_search, "search") as search, \
                    patch.object(config, "LLM_API_KEY", ""):
                answer(question, "auto")
                search.assert_not_called()

    def test_public_questions_choose_web_and_keep_contract(self):
        cases = (*PUBLIC, "比亚迪今年的新能源汽车销量？", "比亚迪去年营收多少？", "特斯拉现在市值多少？")
        parsed = web_search.parse(response_payload())
        for question in cases:
            with self.subTest(question=question), patch.object(web_search, "search", return_value=parsed) as search:
                result = answer(question)
                search.assert_called_once_with(question)
                self.assertEqual(set(result), set(answer_builder.failure("")))
                self.assertEqual((result["ok"], result["mode"], result["intent"]), (True, "llm", ""))
                self.assertEqual((result["data"], result["graph"], result["cypher"]),
                                 ([], {"nodes": [], "edges": []}, ""))
                self.assertIn("公开互联网", result["conclusion"])

    def test_unset_flag_defaults_to_web(self):
        with patch.dict(os.environ), patch.object(
            web_search, "search", return_value=web_search.parse(response_payload())
        ) as search:
            os.environ.pop("QA_WEB_SEARCH_ENABLED", None)
            self.assertTrue(answer(PUBLIC[0])["ok"])
            search.assert_called_once_with(PUBLIC[0])

    def test_vague_requests_and_unrelated_questions_stay_local(self):
        cases = ("目前最厉害的新能源汽车公司是哪个？", "这家公司新能源汽车的销量是多少？",
                 "那家电动汽车厂近期发布了什么产品？", "今天北京天气怎样？")
        for question in cases:
            with self.subTest(question=question), patch.object(web_search, "search") as search, \
                    patch.object(config, "LLM_API_KEY", ""):
                self.assertFalse(answer(question)["ok"])
                search.assert_not_called()

    def test_rule_disabled_and_mock_skip_network(self):
        with patch.object(web_search, "search") as search:
            self.assertIn("规则模式", answer(PUBLIC[0], "rule")["error"])
            with patch.dict(os.environ, QA_WEB_SEARCH_ENABLED="false"):
                self.assertNotIn("规则模式", answer(PUBLIC[0], "rule")["error"])
            with patch.object(config, "QA_BACKEND", "mock"):
                self.assertFalse(answer(PUBLIC[0])["ok"])
            search.assert_not_called()

    def test_local_failures_never_switch_to_web(self):
        for error in (QueryUnavailable("Neo4j 不可用"), ScopeMismatch("范围不符"), FileNotFoundError()):
            with self.subTest(error=error), patch.object(web_search, "search") as search, \
                    patch.object(answer_builder.Retrieval, "retrieve", side_effect=error), \
                    patch.object(answer_builder.cache, "recover", return_value=None), \
                    patch.object(config, "LLM_API_KEY", ""):
                self.assertFalse(answer(intents.EXAMPLES[intents.TOP])["ok"])
                search.assert_not_called()


class WebResponseTests(unittest.TestCase):
    def test_only_linked_content_is_returned(self):
        parsed = web_search.parse(response_payload())
        self.assertEqual((parsed.calls, parsed.searches, parsed.citations, parsed.tokens), (1, 3, 1, 120))
        self.assertIn(URL, parsed.conclusion)
        self.assertIn("2026-01-01", parsed.conclusion)
        self.assertNotIn("数字123", parsed.conclusion)

    def test_citation_numbering_and_missing_metadata(self):
        payload = response_payload()
        message = payload["choices"][0]["message"]
        second_url = "https://www.miit.gov.cn/test-fixture"
        message["server_tool_calls"][0]["calls"][0]["sources"].append({"url": second_url})
        first = message["annotations"][0]
        boundary = first["url_citation"]["end_index"]
        message["annotations"] = [
            {"type": "url_citation", "url_citation": {"url": second_url, "start_index": boundary,
                                                      "end_index": len(message["content"])}},
            first,
        ]
        result = web_search.parse(payload)
        self.assertEqual(result.citations, 2)
        self.assertIn(f"[1](<{URL}>)", result.conclusion)
        self.assertIn(f"[2](<{second_url}>)", result.conclusion)
        self.assertIn(f"2. [www.miit.gov.cn](<{second_url}>) · 日期未提供", result.conclusion)

    def test_http_200_without_verified_evidence_is_failure(self):
        for field, replacement in (("annotations", []), ("server_tool_calls", []),
                                   ("content", ""), ("annotations", [{"type": "url_citation",
                                    "url_citation": {"url": "https://invented.example", "start_index": 0, "end_index": 3}}])):
            with self.subTest(field=field):
                payload = copy.deepcopy(response_payload())
                payload["choices"][0]["message"][field] = replacement
                with self.assertRaises(web_search.SearchUnavailable):
                    web_search.parse(payload)

    def test_latest_sales_checks_statistical_month_in_cited_sentence(self):
        question = "最近的新能源汽车销量"
        today = date.today()
        for content, accepted in (
            (f"{today.year}年{today.month}月5日发布，2020年1月的销量为一万辆。", False),
            (f"{today.year}年{today.month}月新能源汽车销量为一万辆。", True),
        ):
            with self.subTest(accepted=accepted):
                payload = response_payload()
                message = payload["choices"][0]["message"]
                message["content"] = content
                message["annotations"][0]["url_citation"]["end_index"] = len(content)
                if accepted:
                    self.assertIn("一万辆", web_search.parse(payload, question).conclusion)
                else:
                    with self.assertRaisesRegex(web_search.SearchUnavailable, "未核实最近两个月"):
                        web_search.parse(payload, question)

    def test_unsafe_web_urls_are_rejected(self):
        for url in ("javascript:alert(1)", "http://127.0.0.1/log", "http://localhost./",
                    "http://169.254.169.254/", "http://0x7f.0x0.0x0.0x1/", "http://224.0.0.1/",
                    "https://www.miit.gov.cn/notice.html%29%E6%9F%A5%E7%9C%8B%E5%85%A8%E6%96%87",
                    "https://user:pass@example.com/", "https://company.internal/a", "https://example.com\\@other.org"):
            with self.subTest(url=url):
                self.assertIsNone(web_search._url(url))

    def test_no_key_is_explained(self):
        with patch.object(config, "LLM_API_KEY", ""), patch.object(web_search, "_request") as request:
            with self.assertRaisesRegex(web_search.SearchUnavailable, "API Key"):
                web_search.search(PUBLIC[0])
            request.assert_not_called()

    def test_http_errors_timeout_and_request_parameters(self):
        with patch.object(config, "LLM_API_KEY", "test-token"), \
                patch.object(config, "LLM_API_BASE", "https://api.deepseek.com"), \
                patch.object(config, "LLM_MODEL", "deepseek-flash"), \
                patch.object(web_search, "_request") as request:
            for status, message in ((401, "鉴权"), (402, "余额"), (429, "受限"), (500, "请求失败")):
                with self.subTest(status=status):
                    request.return_value = httpx.Response(status, request=httpx.Request("POST", "https://api.deepseek.com"))
                    with self.assertRaisesRegex(web_search.SearchUnavailable, message):
                        web_search.search(PUBLIC[0])
            request.side_effect = httpx.ReadTimeout("test")
            with self.assertRaisesRegex(web_search.SearchUnavailable, "超时"):
                web_search.search(PUBLIC[0])
            body = request.call_args.args[0]
            self.assertEqual(body["tools"], [{"type": "deepseek_web_search"}])
            self.assertEqual(body["thinking"], {"type": "disabled"})
            self.assertFalse({"response_format", "logprobs", "top_logprobs", "tool_choice"} & body.keys())
