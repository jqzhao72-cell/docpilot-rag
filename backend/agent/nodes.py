"""LangGraph nodes and explicit routing for the bounded Agent V1 workflow."""
import json
from queue import Empty, Queue
import re
from threading import BoundedSemaphore, Thread
from time import monotonic

from agent.schemas import FALLBACK, Limits
from agent.state import AgentState
from agent.tools import ToolRegistry


_inflight = BoundedSemaphore(4)
_GREETING = re.compile(r'\s*(你好|您好|hello|hi|谢谢|多谢)[！!。.?？\s]*', re.I)
_FATAL_MODEL_REASONS = {'total_timeout', 'model_timeout', 'model_error', 'max_rounds'}


def bounded_call(action, seconds):
    """Bound read-only work; late results cannot mutate graph state."""
    if seconds <= 0:
        raise TimeoutError()
    if not _inflight.acquire(blocking=False):
        raise RuntimeError('Agent capacity exhausted')
    queue = Queue(maxsize=1)

    def run():
        try:
            queue.put((True, action()))
        except Exception as exc:
            queue.put((False, exc))
        finally:
            _inflight.release()

    Thread(target=run, daemon=True).start()
    try:
        ok, result = queue.get(timeout=seconds)
    except Empty:
        raise TimeoutError() from None
    if not ok:
        raise result
    return result


class AgentNodes:
    """Request-local node set; model and authorized tool closure never enter State."""

    def __init__(self, model, tools: ToolRegistry, limits: Limits):
        self.model = model
        self.tools = tools
        self.limits = limits

    @staticmethod
    def _usage(state, response):
        current = dict(state['usage'])
        response_usage = response.get('usage') or {}
        for key in current:
            current[key] += response_usage.get(key, 0) or 0
        return current

    def _complete(self, state: AgentState, allow_tools: bool):
        remaining = state['deadline'] - monotonic()
        if remaining <= 0:
            return None, {'stop_reason': 'total_timeout', 'error': 'total_timeout'}
        if state['model_call_count'] >= self.limits.max_rounds:
            return None, {'stop_reason': 'max_rounds', 'error': 'max_rounds'}
        began = monotonic()
        try:
            response = bounded_call(
                lambda: self.model.complete(state['messages'], self.tools.definitions,
                                            allow_tools, min(self.limits.request_timeout, remaining)),
                min(self.limits.request_timeout, remaining),
            )
        except TimeoutError:
            reason = 'total_timeout' if monotonic() >= state['deadline'] else 'model_timeout'
            return None, {'model_call_count': state['model_call_count'] + 1,
                          'model_ms': state['model_ms'] + (monotonic() - began) * 1000,
                          'stop_reason': reason, 'error': reason}
        except Exception:
            return None, {'model_call_count': state['model_call_count'] + 1,
                          'model_ms': state['model_ms'] + (monotonic() - began) * 1000,
                          'stop_reason': 'model_error', 'error': 'model_error'}
        return response, {
            'model_call_count': state['model_call_count'] + 1,
            'model_ms': state['model_ms'] + (monotonic() - began) * 1000,
            'usage': self._usage(state, response),
            'latest_finish_reason': response.get('finish_reason'),
        }

    def agent_node(self, state: AgentState):
        allow_tools = (state['tool_attempt_count'] < self.limits.max_searches
                       and state['model_call_count'] < self.limits.max_rounds - 1)
        response, update = self._complete(state, allow_tools)
        if response is None:
            return update
        message = response['message']
        tool_calls = message.get('tool_calls') or []
        if tool_calls:
            update.update(messages=[*state['messages'], message], pending_tool_calls=tool_calls,
                          allow_tool_execution=allow_tools, final_answer=None,
                          stop_reason='running', error=None)
            if not allow_tools:
                update.update(stop_reason='search_limit' if state['tool_attempt_count'] >= self.limits.max_searches
                              else 'max_rounds', error='unexpected_tool_calls')
                return update
            return update
        answer = (message.get('content') or '').strip()
        if response.get('finish_reason') == 'length':
            update.update(stop_reason='model_truncated', error='model_truncated', final_answer=None)
        elif not answer:
            update.update(stop_reason='empty_answer', error='empty_answer', final_answer=None)
        else:
            update.update(final_answer=answer, pending_tool_calls=[],
                          stop_reason='completed' if state['evidence_ledger'] else 'no_evidence')
        return update

    def tool_node(self, state: AgentState):
        messages = list(state['messages'])
        ledger = {key: dict(value) for key, value in state['evidence_ledger'].items()}
        trace = list(state['tool_trace'])
        seen = set(state['seen_tool_call_ids'])
        attempts = state['tool_attempt_count']
        retrievals = state['retrieval_count']
        tool_ms = state['tool_ms']
        reason = state['stop_reason']
        error = state['error']
        calls = state['pending_tool_calls']
        reject_batch = len(calls) > 8

        for call in calls:
            call_id = call.get('id')
            function = call.get('function') or {}
            began = monotonic()
            status, evidence_count = 'ok', 0
            if not isinstance(call_id, str) or not call_id:
                reason, error = 'invalid_tool_call', 'invalid_tool_call'
                continue
            if not state['allow_tool_execution']:
                status = ('search_limit' if attempts >= self.limits.max_searches else 'max_rounds')
                payload = {'error': status}
                reason, error = status, status
            elif reject_batch or call_id in seen:
                payload, status = {'error': 'invalid_tool_call'}, 'invalid_tool_call'
                reason, error = status, status
            elif attempts >= self.limits.max_searches:
                payload, status = {'error': 'search_limit'}, 'search_limit'
                reason, error = status, status
            else:
                seen.add(call_id)
                attempts += 1
                if function.get('name') != 'search_knowledge_base':
                    payload, status = {'error': 'unknown_tool'}, 'unknown_tool'
                    reason, error = 'invalid_tool_call', status
                else:
                    try:
                        args = self.tools.validate(function.get('name'), function.get('arguments'))
                    except Exception:
                        payload, status = {'error': 'invalid_arguments'}, 'invalid_arguments'
                        reason, error = status, status
                    else:
                        retrievals += 1
                        try:
                            payload = bounded_call(
                                lambda args=args: self.tools.execute(args),
                                min(self.limits.tool_timeout, state['deadline'] - monotonic()),
                            )
                            evidence = []
                            for item in payload.get('evidence', [])[:args.top_k]:
                                cid = item['chunk_id']
                                if cid not in ledger:
                                    ledger[cid] = {**item, 'index': len(ledger) + 1}
                                evidence.append(ledger[cid])
                            evidence_count = len(evidence)
                            payload = {'query': args.query, 'has_evidence': bool(evidence), 'evidence': evidence}
                            if not evidence:
                                status = 'no_evidence'
                                reason = 'no_evidence'
                        except TimeoutError:
                            payload, status = {'error': 'tool_timeout'}, 'tool_timeout'
                            reason, error = status, status
                        except Exception:
                            payload, status = {'error': 'tool_error'}, 'tool_error'
                            reason, error = status, status
            elapsed = (monotonic() - began) * 1000
            tool_ms += elapsed
            trace.append({'step': len(trace) + 1, 'tool': 'search_knowledge_base',
                          'status': status, 'evidence_count': evidence_count, 'elapsed_ms': elapsed})
            messages.append({'role': 'tool', 'tool_call_id': call_id,
                             'content': json.dumps(payload, ensure_ascii=False)})

        return {'messages': messages, 'evidence_ledger': ledger, 'tool_trace': trace,
                'seen_tool_call_ids': list(seen), 'tool_attempt_count': attempts,
                'retrieval_count': retrievals, 'tool_ms': tool_ms,
                'pending_tool_calls': [], 'stop_reason': reason, 'error': error}

    def finalize_node(self, state: AgentState):
        update = {}
        final = state['final_answer']
        reason = state['stop_reason']
        # When the last step produced tool messages, make exactly one tools-disabled
        # model call. Fatal model/protocol failures terminate without another call.
        if (not final and state['messages'] and state['messages'][-1].get('role') == 'tool'
                and reason not in _FATAL_MODEL_REASONS | {'invalid_tool_call'}):
            response, model_update = self._complete(state, False)
            update.update(model_update)
            if response is not None:
                message = response['message']
                if message.get('tool_calls'):
                    reason = 'search_limit' if state['tool_attempt_count'] >= self.limits.max_searches else 'invalid_tool_call'
                elif response.get('finish_reason') == 'length':
                    reason = 'model_truncated'
                else:
                    final = (message.get('content') or '').strip() or None
                    if not final:
                        reason = 'empty_answer'
            else:
                reason = model_update['stop_reason']

        sources = []
        if final:
            cited = {int(value) for value in re.findall(r'\[(\d+)\]', final)}
            valid = {source['index'] for source in state['evidence_ledger'].values()}
            if cited - valid:
                final, reason = None, 'invalid_citations'
            elif cited:
                sources = [source for source in state['evidence_ledger'].values()
                           if source['index'] in cited]
                reason = 'completed'
            elif state['evidence_ledger']:
                final, reason = None, 'invalid_citations'
            elif _GREETING.fullmatch(state['question']):
                reason = 'completed'
            else:
                final = None
                if reason == 'completed':
                    reason = 'no_evidence'
        if not final:
            final = FALLBACK
        update.update(final_answer=final, validated_sources=sources, stop_reason=reason,
                      pending_tool_calls=[])
        return update


def route_after_agent(state: AgentState):
    """Model tool calls go to tools; all answers and failures go to finalization."""
    return 'tool_node' if state['pending_tool_calls'] else 'finalize_node'


def route_after_tool(state: AgentState):
    """Continue thinking only while both retrieval and failure budgets permit it."""
    terminal = {'invalid_arguments', 'invalid_tool_call', 'tool_error', 'tool_timeout',
                'search_limit', 'total_timeout', 'max_rounds'}
    if (state['tool_attempt_count'] >= state['max_searches']
            or state['model_call_count'] >= state['max_model_calls']
            or state['stop_reason'] in terminal):
        return 'finalize_node'
    return 'agent_node'
