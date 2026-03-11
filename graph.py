from langgraph.graph import StateGraph, END
from state import AgentState
from agent import agent_node, tool_node
from compare import compare_options


def should_call_tools(state: dict) -> str:
    """
    Routing function: if the agent flagged that it needs more info from the user,
    go straight to END (the clarification message is already in state["recommendation"]).
    Otherwise proceed to tool calls.
    """
    
    if state.get("needs_clarification"):
        return "end"
    return "tools"


def build_graph():
    """
    Builds and compiles the LangGraph agentic workflow.

    Flow:
        agent → (needs_clarification?) → END
                                       → tools → compare → END
    """

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("compare", compare_options)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_call_tools,
        {
            "tools": "tools",
            "end": END,
        },
    )

    workflow.add_edge("tools", "compare")
    workflow.add_edge("compare", END)

    return workflow.compile()