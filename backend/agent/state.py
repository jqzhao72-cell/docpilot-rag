"""Serializable per-request state for the LangGraph Agent V1 workflow."""
from typing import Any, TypedDict


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    evidence_ledger: dict[str, dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    retrieval_count: int
    tool_attempt_count: int
    model_call_count: int
    max_searches: int
    max_model_calls: int
    usage: dict[str, int]
    stop_reason: str
    started_at: float
    deadline: float
    model_ms: float
    tool_ms: float
    final_answer: str | None
    validated_sources: list[dict[str, Any]]
    error: str | None
    pending_tool_calls: list[dict[str, Any]]
    allow_tool_execution: bool
    seen_tool_call_ids: list[str]
    latest_finish_reason: str | None
    permission_context: dict[str, str]
    question: str
