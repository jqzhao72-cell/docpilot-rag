"""Bind authenticated knowledge scope to the Agent; never expose scope as a tool argument."""
from agent.harness import Harness
from agent.model_client import ModelClient
from time import monotonic
import logging


def answer_agent(question, knowledge_base, user_role, history_text=''):
    started = monotonic()
    from app.knowledge import visible_chunks, search_evidence
    chunks = visible_chunks(knowledge_base, user_role)
    model = ModelClient()
    try:
        search = lambda query, top_k: search_evidence(query, top_k, knowledge_base, chunks)
        result = Harness(model, search).run(question, history_text)
        result['timings']['total_ms'] = (monotonic() - started) * 1000
        logging.getLogger(__name__).info('Agent reason=%s retrievals=%d model_calls=%d timings=%s trace=%s',
            result['stop_reason'], result['retrieval_count'], result['model_call_count'],
            result['timings'], result['tool_trace'])
        return result
    finally:
        model.close()
