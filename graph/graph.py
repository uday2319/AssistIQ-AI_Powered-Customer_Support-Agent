from langgraph.graph import StateGraph,START,END
from langgraph.prebuilt import ToolNode
from graph.state import SupportState
from graph.nodes import agent_node
from tools.order_tools import get_order_status
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base

tools=[get_order_status, get_customer, search_knowledge_base]
tool_node=ToolNode(tools)

from langchain_core.messages import AIMessage


def route_after_agent(state: SupportState):
    """
    Decide what the graph should do after the Agent Node.

    Returns:
        "tools" if Gemini requested a tool.
        "end" if Gemini produced a normal response.
    """

    last_message = state["messages"][-1]

     
    if isinstance(last_message, AIMessage) and last_message.tool_calls:

        return "tools"

    return "end"

builder=StateGraph(SupportState)

builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)


builder.add_edge(START,"agent")

builder.add_conditional_edges("agent",route_after_agent,{
    "tools":"tools",
    "end":END

}
)

builder.add_edge("tools","agent")

support_graph=builder.compile()

 