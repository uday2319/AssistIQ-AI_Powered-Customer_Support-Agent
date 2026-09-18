from langchain_google_genai import ChatGoogleGenerativeAI

from config import GOOGLE_API_KEY
from graph.state import SupportState
from tools.order_tools import get_order_status
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base
from tools.cancellation_tools import cancel_order
from langgraph.types import interrupt
from tools.refund_tools import check_refund_eligibility, execute_refund
from langgraph.types import interrupt

from tools.refund_tools import (
    request_refund,
    check_refund_eligibility,
    execute_refund
)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY
)

llm_with_tools=llm.bind_tools([get_order_status, 
                                get_customer, 
                                search_knowledge_base,
                                cancel_order,
                                request_refund
                                ])



def agent_node(state: SupportState):
    """
    Run the LLM using the current conversation state.
    """

    messages = state["messages"]

    response = llm_with_tools.invoke(messages)
 
    return {
        "messages": [response]
    }

def human_approval_node(state:SupportState):
    """
    Pause the workflow and ask a human to approve or reject
    the proposed refund.
    """
    refund_info = state["refund_info"]

    decision = interrupt({
        "type": "refund_approval",
        "message": "Human approval required for this refund.",
        "order_id": refund_info["order_id"],
        "amount": refund_info["amount"],
        "payment_id": refund_info["payment_id"]
    })


    return {
        "human_approval": decision
    }

def refund_eligibility_node(state: SupportState):
    """
    Check whether the requested refund is eligible.
    """

    # Get the order ID prepared by the previous node.
    order_id = state["refund_order_id"]

    # Run deterministic backend validation.
    refund_info = check_refund_eligibility(order_id)

    # Store the result in graph state.
    return {
        "refund_info": refund_info
    }
    

def execute_refund_node(state: SupportState):
    """
    Execute the refund after human approval.
    """

    refund_info = state["refund_info"]

    result = execute_refund(
        payment_id=refund_info["payment_id"],
        amount=refund_info["amount"]
    )

    return {
        "messages": [
            {
                "role": "assistant",
                "content": result["message"]
            }
        ]
    }

def prepare_refund_node(state: SupportState):
    """
    Extract the order ID from Gemini's refund tool call
    and store it in graph state.
    """

    last_message = state["messages"][-1]

    # Find Gemini's request_refund tool call.
    refund_tool_call = next(
        tool_call
        for tool_call in last_message.tool_calls
        if tool_call["name"] == "request_refund"
    )

    # Get the structured order ID.
    order_id = refund_tool_call["args"]["order_id"]

    # Store it in the graph state.
    return {
        "refund_order_id": order_id
    }