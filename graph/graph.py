from langgraph.graph import StateGraph,START,END
from langgraph.prebuilt import ToolNode
from graph.state import SupportState
from tools.order_tools import get_order_status
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base
from tools.cancellation_tools import cancel_order 
from graph.checkpointer import create_checkpointer
from langchain_core.messages import AIMessage
from tools.permissions import READ_TOOLS, ACTION_TOOLS
from tools.refund_tools import (
    request_refund,
    check_refund_eligibility,
    execute_refund
)
from graph.nodes import (
    agent_node,
    refund_eligibility_node,
    human_approval_node,
    execute_refund_node,
    prepare_refund_node,
    prepare_cancellation_node,
    confirm_cancellation_node,
    confirm_refund_reason_node,
    blocked_tool_node,
    cancel_order_node
)
tools=[get_order_status, get_customer, search_knowledge_base]
tool_node=ToolNode(tools)

# Postgres by default, so conversations survive restarts.
# See graph/checkpointer.py.
checkpointer = create_checkpointer()

def route_after_agent(state: SupportState):
    """
    Decide what the graph should do after Gemini responds.

    Gemini can request:
    - read-only tools
    - refund workflow
    - cancellation workflow

    The application decides which path is allowed.
    """

    last_message = state["messages"][-1]
 
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return "end"


    for tool_call in last_message.tool_calls:

        tool_name = tool_call["name"]

        # Routers only choose the next step. They cannot change state,
        # so the order ID is saved by prepare_refund / prepare_cancellation.
        if tool_name == "request_refund":
            return "refund"

        if tool_name == "cancel_order":
            return "cancel"
 
        if tool_name in READ_TOOLS:
            continue

        # Any other tool (unknown, or an action with no safe workflow)
        # is blocked. The customer gets a polite reply, not silence.
        return "blocked"
 
    return "tools"

def route_after_approval(state: SupportState):
    """
    Decide what to do after the human responds.
    """
    # human_approval_node already turned the decision into
    # exactly "approved" or "rejected".
    decision = state["human_approval"]

    if decision == "approved":
        return "approved"
    
    return "rejected"

def route_after_eligibility(state: SupportState):
    """
    Decide whether the refund should continue to human approval.
    """

    refund_info = state["refund_info"]
    if refund_info["eligible"]:
        return "confirm_reason"

    return "end"

def route_after_reason_confirmation(state: SupportState):
    """
    Send the refund to staff only if the customer confirmed the reason.
    """
    if state.get("refund_reason_confirmed"):
        return "approval"

    return "end"

def route_after_confirmation(state: SupportState):
    """
    Cancel only if the customer clearly said yes.
    """
    if state.get("cancel_confirmed"):
        return "confirmed"

    return "end"

builder = StateGraph(SupportState)

builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)
builder.add_node("prepare_refund", prepare_refund_node)
builder.add_node(
    "refund_eligibility",
    refund_eligibility_node
)

builder.add_node(
    "confirm_refund_reason",
    confirm_refund_reason_node
)

builder.add_node(
    "human_approval",
    human_approval_node
)

builder.add_node("blocked_tool", blocked_tool_node)
builder.add_edge("blocked_tool", END)

builder.add_node(
    "execute_refund",
    execute_refund_node
)
builder.add_node(
    "prepare_cancellation",
     prepare_cancellation_node
)

builder.add_node(
    "confirm_cancellation",
    confirm_cancellation_node
)

builder.add_node(
    "cancel_order",
     cancel_order_node
)

builder.add_edge(START, "agent")
builder.add_edge(
    "prepare_refund",
    "refund_eligibility"
)
builder.add_edge("tools", "agent")
builder.add_edge(
    "prepare_cancellation",
    "confirm_cancellation"
)

builder.add_conditional_edges(
    "confirm_cancellation",
    route_after_confirmation,
    {
        "confirmed": "cancel_order",
        "end": END
    }
)

builder.add_edge(
    "cancel_order",
    END
)
builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "refund": "prepare_refund",
        "cancel": "prepare_cancellation",
        "blocked": "blocked_tool",
        "end": END
    }
)

builder.add_conditional_edges(
    "refund_eligibility",
    route_after_eligibility,
    {
        "confirm_reason": "confirm_refund_reason",
        "end": END
    }
)

builder.add_conditional_edges(
    "confirm_refund_reason",
    route_after_reason_confirmation,
    {
        "approval": "human_approval",
        "end": END
    }
)


builder.add_conditional_edges(
    "human_approval",
    route_after_approval,
    {
        "approved": "execute_refund",
        "rejected": END
    }
)

builder.add_edge("execute_refund", END)


support_graph = builder.compile(
    checkpointer=checkpointer
)
 