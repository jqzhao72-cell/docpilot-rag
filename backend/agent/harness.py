"""Compatibility facade that invokes the compiled LangGraph Agent V1 workflow."""
from time import monotonic

from agent.graph import build_agent_graph
from agent.nodes import AgentNodes
from agent.schemas import FALLBACK, SYSTEM, Limits
from agent.tools import ToolRegistry

__all__ = ['Harness', 'Limits', 'FALLBACK', 'SYSTEM']


class Harness:
    def __init__(self, model, search, limits=None, permission_context=None):
        self.model = model
        self.tools = ToolRegistry(search)
        self.limits = limits or Limits.from_env()
        self.permission_context = dict(permission_context or {'scope': 'server_bound'})
        self.graph = build_agent_graph(AgentNodes(self.model, self.tools, self.limits))

    def run(self, question, history_text=''):
        started = monotonic()
        messages = [{'role': 'system', 'content': SYSTEM}]
        if history_text:
            messages.append({'role': 'user', 'content': '仅作指代背景的历史问题：\n' + history_text[-6000:]})
        messages.append({'role': 'user', 'content': question})
        initial = {
            'messages': messages,
            'evidence_ledger': {},
            'tool_trace': [],
            'retrieval_count': 0,
            'tool_attempt_count': 0,
            'model_call_count': 0,
            'max_searches': self.limits.max_searches,
            'max_model_calls': self.limits.max_rounds,
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0},
            'stop_reason': 'running',
            'started_at': started,
            'deadline': started + self.limits.total_timeout,
            'model_ms': 0.0,
            'tool_ms': 0.0,
            'final_answer': None,
            'validated_sources': [],
            'error': None,
            'pending_tool_calls': [],
            'allow_tool_execution': True,
            'seen_tool_call_ids': [],
            'latest_finish_reason': None,
            'permission_context': dict(self.permission_context),
            'question': question,
        }
        state = self.graph.invoke(initial, config={'recursion_limit': self.limits.max_rounds * 3 + 5})
        return {
            'answer': state['final_answer'] or FALLBACK,
            'sources': state['validated_sources'],
            'tool_trace': state['tool_trace'],
            'timings': {'model_ms': state['model_ms'], 'tool_ms': state['tool_ms'],
                        'total_ms': (monotonic() - started) * 1000},
            'stop_reason': state['stop_reason'],
            'retrieval_count': state['retrieval_count'],
            'model_call_count': state['model_call_count'],
            'usage': state['usage'],
        }
