"""Agent contracts: tool protocol, bounded work, citation ledger and shared retrieval."""
import copy
from concurrent.futures import ThreadPoolExecutor
import ast
import inspect
import json
import textwrap
import time
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from agent.harness import Harness, Limits, FALLBACK
from agent.model_client import ModelClient
from agent.tools import SearchArguments


EVIDENCE = {'chunk_id': 'paper-737', 'id': 'paper-737', 'text': 'GENIE3 infers regulatory networks.',
            'source': 'journal.pone.0297260 (1).pdf', 'page': '2', 'page_start': 2, 'page_end': 2,
            'section': 'Methods', 'chunk_type': 'text', 'knowledge_base': 'paper'}


def call(call_id='c1', arguments=None, name='search_knowledge_base'):
    return {'id': call_id, 'type': 'function', 'function': {'name': name,
        'arguments': json.dumps(arguments or {'query': 'GENIE3', 'top_k': 5})}}


def response(content=None, calls=None):
    message = {'role': 'assistant', 'content': content}
    if calls:
        message['tool_calls'] = calls
    return {'message': message, 'finish_reason': 'tool_calls' if calls else 'stop', 'usage': {}}


class FakeModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def complete(self, messages, tools, allow_tools, timeout):
        self.calls.append((copy.deepcopy(messages), allow_tools))
        return next(self.replies)

    def close(self):
        pass


def found(query, top_k):
    return {'query': query, 'has_evidence': True, 'evidence': [dict(EVIDENCE)]}


class HarnessTests(unittest.TestCase):
    def test_langgraph_topology_and_harness_has_no_agent_loop(self):
        harness = Harness(FakeModel([response('你好！')]), found)
        graph = harness.graph.get_graph()
        self.assertTrue({'agent_node', 'tool_node', 'finalize_node'}.issubset(graph.nodes))
        edges = {(edge.source, edge.target) for edge in graph.edges}
        self.assertIn(('__start__', 'agent_node'), edges)
        self.assertIn(('finalize_node', '__end__'), edges)
        tree = ast.parse(textwrap.dedent(inspect.getsource(Harness.run)))
        self.assertFalse(any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)))

    def test_one_search_real_source_and_tool_call_id(self):
        model = FakeModel([response(calls=[call()]), response('GENIE3 推断调控网络[1]。')])
        result = Harness(model, found).run('GENIE3 有什么职责？')
        self.assertEqual(result['retrieval_count'], 1)
        self.assertEqual(result['model_call_count'], 2)
        self.assertEqual(result['stop_reason'], 'completed')
        self.assertEqual(result['sources'][0]['source'], EVIDENCE['source'])
        self.assertEqual(result['sources'][0]['chunk_id'], 'paper-737')
        self.assertEqual(result['sources'][0]['page'], '2')
        messages = model.calls[1][0]
        self.assertEqual(messages[-2]['tool_calls'][0]['id'], messages[-1]['tool_call_id'])
        self.assertNotIn('text', result['tool_trace'][0])

    def test_second_search_can_recover_empty_first_search(self):
        results = iter([{'evidence': []}, found('', 5)])
        model = FakeModel([response(calls=[call('c1')]), response(calls=[call('c2')]), response('调控网络[1]。')])
        result = Harness(model, lambda *_: next(results)).run('方法是什么？')
        self.assertEqual(result['retrieval_count'], 2)
        self.assertEqual(result['model_call_count'], 3)
        self.assertFalse(model.calls[-1][1])
        self.assertEqual(len(result['sources']), 1)

    def test_no_evidence_never_returns_memory_answer(self):
        model = FakeModel([response(calls=[call('c1')]), response(calls=[call('c2')]), response('凭记忆得到的答案')])
        result = Harness(model, lambda *_: {'evidence': []}).run('未知事实？')
        self.assertEqual(result['answer'], FALLBACK)
        self.assertEqual(result['sources'], [])
        self.assertEqual(result['stop_reason'], 'no_evidence')

    def test_retrieval_budget_applies_to_parallel_tool_calls(self):
        calls = [call('c' + str(i)) for i in range(3)]
        model = FakeModel([response(calls=calls), response('网络[1]。')])
        result = Harness(model, found).run('问题')
        self.assertEqual(result['retrieval_count'], 2)
        tools = [m for m in model.calls[-1][0] if m['role'] == 'tool']
        self.assertEqual([m['tool_call_id'] for m in tools], ['c0', 'c1', 'c2'])
        self.assertEqual(json.loads(tools[-1]['content'])['error'], 'search_limit')
        self.assertEqual([step['status'] for step in result['tool_trace']], ['ok', 'ok', 'search_limit'])
        self.assertEqual(result['stop_reason'], 'completed')

    def test_invalid_parameters_cannot_set_identity_or_scope(self):
        for args in ({'query': 'x', 'user_id': 3}, {'query': 'x', 'role': 'admin'},
                     {'query': 'x', 'top_k': True}, {'query': 'x', 'top_k': 6},
                     {'query': '   '}, {'query': 123}):
            with self.subTest(args=args):
                model = FakeModel([response(calls=[call(arguments=args)]), response('没有可验证证据')])
                with patch('agent.tools.ToolRegistry.execute') as execute:
                    result = Harness(model, found).run('问题')
                execute.assert_not_called()
                self.assertEqual(result['stop_reason'], 'invalid_arguments')
                self.assertEqual(result['retrieval_count'], 0)

    def test_invalid_json_and_unknown_tool(self):
        invalid = call(); invalid['function']['arguments'] = '{bad'
        for tool in (invalid, call(name='http_request')):
            result = Harness(FakeModel([response(calls=[tool]), response('')]), found).run('x')
            self.assertEqual(result['answer'], FALLBACK)
            self.assertEqual(result['retrieval_count'], 0)

    def test_tool_error_is_sanitized_and_model_can_finish(self):
        def error(*_):
            raise ValueError('private-path secret-token')
        model = FakeModel([response(calls=[call()]), response('无法取得证据')])
        result = Harness(model, error).run('x')
        self.assertEqual(result['stop_reason'], 'tool_error')
        self.assertNotIn('secret-token', json.dumps(result))
        self.assertNotIn('secret-token', json.dumps(model.calls[-1]))

    def test_tool_timeout(self):
        def slow(*_):
            time.sleep(0.06)
            return found('', 5)
        model = FakeModel([response(calls=[call()]), response('无法取得证据')])
        result = Harness(model, slow, Limits(tool_timeout=0.01)).run('x')
        self.assertEqual(result['stop_reason'], 'tool_timeout')
        self.assertEqual(result['sources'], [])

    def test_total_timeout_and_model_timeout(self):
        class SlowModel:
            def complete(self, *_):
                time.sleep(0.06)
                return response('late')
        for limits, reason in ((Limits(total_timeout=0.01), 'total_timeout'),
                               (Limits(request_timeout=0.01), 'model_timeout')):
            result = Harness(SlowModel(), found, limits).run('x')
            self.assertEqual(result['stop_reason'], reason)
            self.assertEqual(result['answer'], FALLBACK)

    def test_fabricated_citations_or_missing_citations_rejected(self):
        for answer in ('错误来源[99]。', '没有引用的结论'):
            model = FakeModel([response(calls=[call()]), response(answer)])
            result = Harness(model, found).run('问题')
            self.assertEqual(result['stop_reason'], 'invalid_citations')
            self.assertEqual(result['sources'], [])
            self.assertEqual(result['answer'], FALLBACK)

    def test_no_tool_greeting_and_no_tool_unsupported_fact(self):
        greeting = Harness(FakeModel([response('你好！')]), found).run('你好')
        self.assertEqual(greeting['retrieval_count'], 0)
        self.assertEqual(greeting['answer'], '你好！')
        result = Harness(FakeModel([response('编造的知识答案')]), found).run('论文结果是什么？')
        self.assertEqual(result['answer'], FALLBACK)

    def test_duplicate_tool_id_stops_protocol(self):
        model = FakeModel([response(calls=[call(), call()])])
        result = Harness(model, found).run('x')
        self.assertEqual(result['stop_reason'], 'invalid_tool_call')

    def test_model_budget_rejects_late_tool_call_without_execution(self):
        model = FakeModel([response(calls=[call('c1')]), response(calls=[call('late')])])
        searches = []
        def empty(*args):
            searches.append(args)
            return {'evidence': []}
        result = Harness(model, empty, Limits(max_rounds=2)).run('x')
        self.assertEqual(result['model_call_count'], 2)
        self.assertEqual(result['retrieval_count'], 1)
        self.assertEqual(len(searches), 1)
        self.assertEqual(result['tool_trace'][-1]['status'], 'max_rounds')

    def test_usage_statistics_and_concurrent_state_are_isolated(self):
        def run(label):
            evidence = {**EVIDENCE, 'chunk_id': label, 'id': label, 'source': label + '.pdf'}
            first = response(calls=[call(label)])
            first['usage'] = {'prompt_tokens': 7, 'completion_tokens': 2}
            second = response(f'{label}[1]。')
            second['usage'] = {'prompt_tokens': 11, 'completion_tokens': 3}
            model = FakeModel([first, second])
            result = Harness(model, lambda *_: {'evidence': [evidence]}).run(label)
            return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            left, right = list(pool.map(run, ('left', 'right')))
        self.assertEqual(left['usage'], {'prompt_tokens': 18, 'completion_tokens': 5})
        self.assertEqual(right['usage'], {'prompt_tokens': 18, 'completion_tokens': 5})
        self.assertEqual([source['chunk_id'] for source in left['sources']], ['left'])
        self.assertEqual([source['chunk_id'] for source in right['sources']], ['right'])
        self.assertEqual(left['retrieval_count'], 1)
        self.assertEqual(left['model_call_count'], 2)


class ModelClientTests(unittest.TestCase):
    def test_sdk_tool_roundtrip_with_mock_http_transport(self):
        requests = []
        def handle(request):
            payload = json.loads(request.content)
            requests.append(payload)
            message = response(calls=[call()])['message'] if len(requests) == 1 else response('网络[1]。')['message']
            return httpx.Response(200, json={'id': 'completion1', 'object': 'chat.completion', 'created': 1,
                'model': 'deepseek-chat', 'choices': [{'index': 0, 'message': message,
                    'finish_reason': 'tool_calls' if len(requests) == 1 else 'stop'}]})
        client = OpenAI(api_key='test-only', base_url='https://provider.invalid',
                        http_client=httpx.Client(transport=httpx.MockTransport(handle)), max_retries=0)
        model = ModelClient(client)
        try:
            result = Harness(model, found).run('GENIE3 职责？')
        finally:
            model.close()
        self.assertEqual(result['model_call_count'], 2)
        self.assertEqual(result['retrieval_count'], 1)
        self.assertEqual(requests[1]['messages'][-1]['tool_call_id'], 'c1')
        self.assertNotIn('parallel_tool_calls', requests[0])
        self.assertNotIn('response_format', requests[0])


if __name__ == '__main__':
    unittest.main()
