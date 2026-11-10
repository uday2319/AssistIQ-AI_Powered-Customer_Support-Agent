from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import interrupt

from config import GOOGLE_API_KEY, GEMINI_MODEL
from db.queries import CANCELLABLE_STATUSES, find_order
from db.queries import cancel_order as cancel_order_in_db
from graph.state import SupportState
from prompts import build_system_prompt
from tools.cancellation_tools import cancel_order as cancel_order_tool
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base
from tools.order_tools import get_order_status
from tools.refund_tools import (
    request_refund,
    check_refund_eligibility,
    execute_refund
)

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
    max_retries=2
)

llm_with_tools = llm.bind_tools([
    get_order_status,
    get_customer,
    search_knowledge_base,
    cancel_order_tool,
    request_refund
])


# Words a staff member may use to approve a refund.
APPROVAL_WORDS = {"approved", "approve", "accepted", "accept", "yes"}


def normalize_decision(decision) -> str:
    """
    Turn whatever the human sent ("Approved", "accepted", "yes", ...)
    into exactly "approved" or "rejected".
    Anything unclear counts as "rejected" so money never moves by mistake.
    """
    if str(decision).strip().lower() in APPROVAL_WORDS:
        return "approved"
    return "rejected"


# Words that count as the customer saying "yes" to a cancellation.
YES_WORDS = {"yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed"}
# If any of these appear, we treat the answer as "no" to be safe.
NO_WORDS = {"no", "not", "don't", "dont", "wait", "stop", "keep"}


def is_yes(answer) -> bool:
    """
    True only for a clear yes ("yes", "Yes please", "ok, cancel it").
    Anything unclear keeps the order, because cancelling can't be undone.
    """
    words = str(answer).lower().replace(",", " ").replace(".", " ").replace("!", " ").split()
    return bool(words) and words[0] in YES_WORDS and not NO_WORDS.intersection(words)


def answer_tool_calls(message: AIMessage, handled_tool: str, note: str) -> list[ToolMessage]:
    """
    Gemini expects every tool call to get a matching tool reply.
    The refund and cancellation workflows do not go through ToolNode,
    so we add the replies ourselves. Without them, the next message
    in the same conversation can fail.
    """
    replies = []

    for tool_call in message.tool_calls:
        if tool_call["name"] == handled_tool:
            content = note
        else:
            content = "Skipped: another action was handled in this step."

        replies.append(
            ToolMessage(
                content=content,
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
        )

    return replies


def agent_node(state: SupportState):
    """
    Run the LLM using the system prompt and the conversation so far.
    The system prompt is added on every call but not saved in state.
    """

    messages = [SystemMessage(content=build_system_prompt())] + state["messages"]

    response = llm_with_tools.invoke(messages)

    return {
        "messages": [response]
    }


def human_approval_node(state: SupportState):
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

    decision = normalize_decision(decision)

    update = {"human_approval": decision}

    if decision == "rejected":
        update["messages"] = [
            AIMessage(
                content=(
                    f"Sorry, your refund request for order "
                    f"{refund_info['order_id']} was not approved. "
                    "A support agent can help if you have questions."
                )
            )
        ]

    return update


def refund_eligibility_node(state: SupportState):
    """
    Check whether the requested refund is eligible.
    If it is not, tell the customer why.
    """

    order_id = state["refund_order_id"]
    customer_id = state["customer_id"]

    refund_info = check_refund_eligibility(order_id, customer_id)

    update = {"refund_info": refund_info}

    if not refund_info["eligible"]:
        update["messages"] = [
            AIMessage(
                content=f"I couldn't start a refund. {refund_info['message']}"
            )
        ]

    return update


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
            AIMessage(
                content=(
                    f"Good news! Your refund of {result['amount']:.2f} for order "
                    f"{refund_info['order_id']} has been approved and processed. "
                    "It usually reaches your original payment method "
                    "within 5-7 business days."
                )
            )
        ]
    }


def prepare_refund_node(state: SupportState):
    """
    Extract the order ID from Gemini's refund tool call
    and store it in graph state.
    """

    last_message = state["messages"][-1]

    refund_tool_call = next(
        tool_call
        for tool_call in last_message.tool_calls
        if tool_call["name"] == "request_refund"
    )

    order_id = refund_tool_call["args"]["order_id"]

    return {
        "refund_order_id": order_id,
        "messages": answer_tool_calls(
            last_message,
            "request_refund",
            f"Refund request for order {order_id} received. Checking eligibility."
        )
    }


def prepare_cancellation_node(state: SupportState):
    """
    Extract the order ID requested by Gemini.

    The order ID comes from Gemini because it is the customer's
    requested target.

    The customer ID does NOT come from Gemini.
    It comes from trusted application state.
    """

    last_message = state["messages"][-1]

    cancellation_tool_call = next(
        tool_call
        for tool_call in last_message.tool_calls
        if tool_call["name"] == "cancel_order"
    )

    order_id = cancellation_tool_call["args"]["order_id"]

    return {
        "cancel_order_id": order_id,
        "messages": answer_tool_calls(
            last_message,
            "cancel_order",
            f"Cancellation request for order {order_id} received."
        )
    }


def confirm_cancellation_node(state: SupportState):
    """
    Ask the customer to confirm before cancelling, because a
    cancellation cannot be undone.

    First check the order exists and can still be cancelled,
    so we never ask "are you sure?" about an order we can't cancel.
    """

    order_id = state["cancel_order_id"]
    customer_id = state["customer_id"]

    order = find_order(order_id, customer_id)

    if order is None:
        return {
            "cancel_confirmed": False,
            "messages": [
                AIMessage(content=f"Sorry, I couldn't find order {order_id} on your account.")
            ],
        }

    if order["status"] not in CANCELLABLE_STATUSES:
        return {
            "cancel_confirmed": False,
            "messages": [
                AIMessage(
                    content=(
                        f"Order {order_id} is already {order['status']}, so it can't be "
                        "cancelled. If it has shipped, you can request a refund "
                        "after it arrives."
                    )
                )
            ],
        }

    # Pause here until the customer answers.
    answer = interrupt({
        "type": "cancel_confirmation",
        "order_id": order_id,
        "status": order["status"],
        "message": (
            f"Order {order_id} is currently {order['status']}. "
            "Are you sure you want to cancel it? Please reply yes or no."
        ),
    })

    if is_yes(answer):
        return {"cancel_confirmed": True}

    return {
        "cancel_confirmed": False,
        "messages": [
            AIMessage(
                content=(
                    f"Okay, I haven't cancelled order {order_id}. "
                    "Is there anything else I can help with?"
                )
            )
        ],
    }


def cancel_order_node(state: SupportState):
    """
    Execute cancellation using the trusted customer ID.
    """

    order_id = state["cancel_order_id"]
    customer_id = state["customer_id"]

    result = cancel_order_in_db(
        order_id=order_id,
        customer_id=customer_id
    )

    if result["success"]:
        text = f"Your order {order_id} has been cancelled."
    elif result.get("code") == "ORDER_NOT_CANCELLABLE":
        text = (
            f"Sorry, order {order_id} can't be cancelled anymore "
            "(it may have already shipped or been cancelled). "
            "If it has shipped, you can request a refund after it arrives."
        )
    else:
        text = f"Sorry, I couldn't find order {order_id} on your account."

    return {
        "cancel_result": result,
        "messages": [AIMessage(content=text)]
    }
