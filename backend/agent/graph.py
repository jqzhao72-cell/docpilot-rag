"""Explicit LangGraph topology for Agent V1; no persistence/checkpointer."""
from langgraph.graph import END, START, StateGraph

from agent.nodes import AgentNodes, route_after_agent, route_after_tool
from agent.state import AgentState


def build_agent_graph(nodes: AgentNodes):
    workflow = StateGraph(AgentState)
    workflow.add_node('agent_node', nodes.agent_node)
    workflow.add_node('tool_node', nodes.tool_node)
    workflow.add_node('finalize_node', nodes.finalize_node)
    workflow.add_edge(START, 'agent_node')
    workflow.add_conditional_edges('agent_node', route_after_agent, {
        'tool_node': 'tool_node',
        'finalize_node': 'finalize_node',
    })
    workflow.add_conditional_edges('tool_node', route_after_tool, {
        'agent_node': 'agent_node',
        'finalize_node': 'finalize_node',
    })
    workflow.add_edge('finalize_node', END)
    return workflow.compile()
