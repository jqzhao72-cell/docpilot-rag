"""Agent HTTP regression on the same isolated DB/session fixture as fixed RAG."""
from unittest.mock import patch

from tests import test_permissions as permissions
from tests.test_agent import FakeModel, response, call, EVIDENCE, found
from app.models import Message, AuthSession


class AgentApiTests(permissions.ApiTests):
    def ask(self, cid, actor_role='employee', **extra):
        return self.client.post('/agent/chat', json={'question': 'GENIE3?', 'conversation_id': cid, **extra},
                                headers=self.headers[actor_role])

    def test_agent_auth_ownership_and_body_forbid_identity(self):
        cid = self.conversation()
        self.assertEqual(self.client.post('/agent/chat', json={'question': 'x', 'conversation_id': cid}).status_code, 401)
        with patch('app.agent_service.answer_agent') as answer:
            self.assertEqual(self.ask(cid, actor_role='hr').status_code, 404)
            answer.assert_not_called()
        for extra in ({'user_id': 3}, {'role': 'admin'}, {'knowledge_base': 'paper'}):
            self.assertEqual(self.ask(cid, **extra).status_code, 422)

    def test_agent_permission_snapshot_trace_and_existing_history(self):
        cid = self.conversation()
        chunks = [{'id': 'public', 'source': 'public.pdf', 'role': 'employee', 'text': 'public'},
                  {'id': 'private', 'source': 'private.pdf', 'role': 'admin', 'text': 'TOP_SECRET'}]
        def search(query, top_k, base, authorized):
            self.assertEqual([c['id'] for c in authorized], ['public'])
            return {'query': query, 'has_evidence': True, 'evidence': [{**EVIDENCE,
                'id': 'public', 'chunk_id': 'public', 'source': 'public.pdf', 'text': 'public'}]}
        model = FakeModel([response(calls=[call()]), response('结果[1]。')])
        with patch('app.knowledge.read_chunks', return_value=chunks), \
             patch('app.knowledge.search_evidence', side_effect=search), \
             patch('app.agent_service.ModelClient', return_value=model):
            reply = self.ask(cid)
        self.assertEqual(reply.status_code, 200, reply.text)
        payload = reply.json()
        self.assertEqual(payload['retrieval_count'], 1)
        self.assertEqual(payload['sources'][0]['source'], 'public.pdf')
        self.assertNotIn('TOP_SECRET', str(model.calls))
        self.assertNotIn('TOP_SECRET', reply.text)
        messages = self.client.get(f'/conversations/{cid}/messages', headers=self.headers['employee']).json()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]['sources'][0]['id'], 'public')
        self.assertEqual(messages[-1]['tool_trace'][0]['evidence_count'], 1)
        self.assertEqual(messages[-1]['retrieval_count'], 1)
        history = self.client.get('/history', headers=self.headers['employee']).json()
        self.assertEqual(history[0]['answer'], '结果[1]。')
        self.assertEqual(self.client.get('/history', headers=self.headers['hr']).json(), [])

    def test_agent_session_revoked_during_generation_returns_nothing(self):
        cid = self.conversation()
        def revoke(*_):
            with self.factory() as db:
                db.query(AuthSession).filter_by(user_id=1).delete()
                db.commit()
            return {'answer': 'must not leak', 'sources': []}
        with patch('app.agent_service.answer_agent', side_effect=revoke):
            reply = self.ask(cid)
        self.assertEqual(reply.status_code, 401)
        with self.factory() as db:
            self.assertEqual(db.query(Message).count(), 0)
