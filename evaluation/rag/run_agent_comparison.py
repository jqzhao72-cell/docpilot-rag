"""One-question HTTP comparison on an isolated DB with the real authorized corpus.

Explicit --live sends this question and retrieved accessible paper excerpts to the
configured backend provider. No application users/conversations are changed.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, BACKEND_ROOT, get_db
from app.main import app
from app.models import User, Conversation
from app.auth import issue_session

ROOT = Path(__file__).resolve().parents[2]
QUESTION = 'GENIE3、RcisTarget 和 AUCell 分别承担什么职责？'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--mock', action='store_true', help='Real retrieval and HTTP routes, simulated models; no external calls')
    parser.add_argument('--preview', action='store_true', help='Only save the question and real local evidence for review')
    args = parser.parse_args()
    load_dotenv(BACKEND_ROOT / '.env')
    output = ROOT / 'evaluation/reports/rag' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-agent-v1')
    output.mkdir(parents=True, exist_ok=False)
    result = {'question': QUESTION, 'status': 'running', 'live_requested': args.live, 'runs': {}}
    path = output / 'comparison.json'
    result['model_mode'] = 'simulated' if args.mock else 'live'
    if args.preview:
        from app.knowledge import visible_chunks, search_evidence, knowledge_lock
        with knowledge_lock():
            preview = search_evidence(QUESTION, 5, 'paper', visible_chunks('paper', 'admin'))
        result.update(status='preview_only', model_calls=0, destination='https://api.deepseek.com', preview=preview)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(path)
        return
    if not args.mock and (not args.live or not (os.getenv('DEEPSEEK_API_KEY') or os.getenv('AGENT_API_KEY'))):
        result.update(status='blocked', reason='Use --live with backend model credentials; no key is recorded.')
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(path)
        return
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    patches = []
    model_audit = []
    try:
        if args.live:
            from agent.model_client import ModelClient as LiveModelClient
            from agent.tools import SearchArguments
            class AuditedModelClient(LiveModelClient):
                def complete(self, messages, tools, allow_tools, timeout):
                    began = perf_counter()
                    response = super().complete(messages, tools, allow_tools, timeout)
                    calls = []
                    for call in response['message'].get('tool_calls') or []:
                        function = call.get('function') or {}
                        try:
                            parsed = json.loads(function.get('arguments') or '{}')
                        except (TypeError, json.JSONDecodeError):
                            parsed = {'invalid_json': True}
                        # Only the public tool schema fields are persisted. Never record
                        # headers, credentials, identity context or arbitrary messages.
                        safe_args = {key: parsed[key] for key in ('query', 'top_k') if key in parsed}
                        try:
                            effective = SearchArguments.model_validate(parsed).model_dump()
                            schema_validation = 'passed'
                        except Exception:
                            effective, schema_validation = {}, 'failed'
                        calls.append({'tool_call_id': call.get('id'), 'name': function.get('name'),
                                      'arguments': safe_args, 'effective_arguments': effective,
                                      'schema_validation': schema_validation})
                    model_audit.append({
                        'round': len(model_audit) + 1,
                        'elapsed_ms': (perf_counter() - began) * 1000,
                        'allow_tools': allow_tools,
                        'finish_reason': response.get('finish_reason'),
                        'tool_calls': calls,
                        'tool_result_ids_in_request': [m.get('tool_call_id') for m in messages
                                                       if m.get('role') == 'tool'],
                    })
                    return response
            patches.append(patch('app.agent_service.ModelClient', AuditedModelClient))
            patches[-1].start()
        if args.mock:
            from app.knowledge import reranker_component
            class LocalLLM:
                def generate(self, prompt):
                    return '本地模拟回答：SCENIC 通过推断调控网络、筛选调控关系及计算活性完成分析[1]。'
            class LocalModel:
                def __init__(self):
                    self.count = 0
                def complete(self, messages, tools, allow_tools, timeout):
                    self.count += 1
                    if self.count == 1:
                        return {'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                            {'id': 'mock-search', 'type': 'function', 'function': {'name': 'search_knowledge_base',
                             'arguments': json.dumps({'query': QUESTION, 'top_k': 5})}}]}, 'finish_reason': 'tool_calls'}
                    return {'message': {'role': 'assistant', 'content': LocalLLM().generate('')}, 'finish_reason': 'stop'}
                def close(self):
                    pass
            patches = [patch('app.knowledge.generation_components', lambda: (reranker_component(), LocalLLM())),
                       patch('app.agent_service.ModelClient', LocalModel)]
            for item in patches:
                item.start()
        with factory() as db:
            user = User(username='isolated-agent-evaluation', password='unused', role='admin')
            db.add(user)
            db.commit()
            token = issue_session(db, user)['access_token']
            conversations = []
            for mode in ('rag', 'agent'):
                c = Conversation(user_id=user.id, title=mode, knowledge_base='paper')
                db.add(c)
                db.flush()
                conversations.append(c.id)
            db.commit()
        # Measure cold model preparation separately so both HTTP requests are warm.
        from app.knowledge import generation_components, visible_chunks, search_evidence
        started = perf_counter()
        generation_components()
        corpus = {x['id']: x for x in visible_chunks('paper', 'admin')}
        search_evidence(QUESTION, 5, 'paper', list(corpus.values()))
        result['warmup_retrievals'] = 1
        result['cold_preparation_ms'] = (perf_counter() - started) * 1000
        client = TestClient(app)
        for mode, endpoint, cid in zip(('rag', 'agent'), ('/chat', '/agent/chat'), conversations):
            started = perf_counter()
            reply = client.post(endpoint, json={'question': QUESTION, 'conversation_id': cid},
                                headers={'Authorization': 'Bearer ' + token})
            elapsed = (perf_counter() - started) * 1000
            body = reply.json()
            if reply.status_code == 200:
                for source in body['sources']:
                    chunk = corpus[source['id']]
                    if source['source'] != chunk['source'] or source['page_start'] != chunk.get('page_start') or source['page_end'] != chunk.get('page_end'):
                        raise ValueError('Citation does not match accessible corpus')
                body['source_validation'] = 'passed'
                if mode == 'rag':
                    body['retrieval_count'] = 1
                    body['model_call_count'] = 1
            result['runs'][mode] = {'status_code': reply.status_code, 'http_total_ms': elapsed, **body}
            if mode == 'agent':
                result['runs'][mode]['model_rounds'] = model_audit
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(mode, reply.status_code, 'http_total_ms', round(elapsed, 1), flush=True)
        client.close()
        agent = result['runs']['agent']
        result['status'] = 'completed' if (all(x['status_code'] == 200 for x in result['runs'].values())
            and agent.get('retrieval_count', 0) >= 1 and agent.get('model_call_count', 0) >= 2
            and bool(agent.get('sources'))) else 'failed_or_inconclusive'
    except Exception as exc:
        result.update(status='failed', error_type=type(exc).__name__)
        raise
    finally:
        for item in reversed(patches):
            item.stop()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Report:', path, flush=True)


if __name__ == '__main__':
    main()
