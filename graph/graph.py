from langgraph.graph import StateGraph,START,END
from langgraph.prebuilt import ToolNode
from graph.state import SupportState
from tools.order_tools import get_order_status
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base
from tools.cancellation_tools import cancel_order 
from langgraph.checkpoint.memory import MemorySaver
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
    cancel_order_node
)
tools=[get_order_status, get_customer, search_knowledge_base]
tool_node=ToolNode(tools)

checkpointer=MemorySaver()

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
        if tool_name == "request_refund":

            order_id = tool_call["args"]["order_id"]
            state["refund_order_id"] = order_id
 
            return "refund"
 
        if tool_name == "cancel_order":

            order_id = tool_call["args"]["order_id"]

            state["cancel_order_id"] = order_id
 
            return "cancel"
 
        if tool_name in ACTION_TOOLS: 
            return "end"
 
        if tool_name in READ_TOOLS:
            continue

        return "end"
 
    return "tools"

def route_after_approval(state: SupportState):
    """
    Decide what to do after the human responds.
    """
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
        return "approval"

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
    "human_approval",
    human_approval_node
)

builder.add_node(
    "execute_refund",
    execute_refund_node
)
builder.add_node(
    "prepare_cancellation",
     prepare_cancellation_node
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
    "cancel_order"
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
        "end": END
    }
)

builder.add_conditional_edges(
    "refund_eligibility",
    route_after_eligibility,
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
 