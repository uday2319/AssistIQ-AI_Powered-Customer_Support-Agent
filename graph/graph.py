from langgraph.graph import StateGraph,START,END
from langgraph.prebuilt import ToolNode
from graph.state import SupportState
from tools.order_tools import get_order_status
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base
from tools.cancellation_tools import cancel_order 
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage

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
    prepare_refund_node
)
tools=[get_order_status, get_customer, search_knowledge_base,cancel_order]
tool_node=ToolNode(tools)

checkpointer=MemorySaver()

def route_after_agent(state: SupportState):

    last_message = state["messages"][-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:

        for tool_call in last_message.tool_calls:

            tool_name = tool_call["name"]

            if tool_name == "request_refund":

                # Extract the order ID Gemini supplied
                # in the structured tool call.
                order_id = tool_call["args"]["order_id"]

                # Store it in the graph state.
                state["refund_order_id"] = order_id

                return "refund"

        return "tools"

    return "end"

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


builder.add_edge(START, "agent")
builder.add_edge(
    "prepare_refund",
    "refund_eligibility"
)
builder.add_edge("tools", "agent")

builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "refund": "prepare_refund",
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
 