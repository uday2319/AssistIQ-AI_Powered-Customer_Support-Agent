import hmac
import json

from fastapi import FastAPI, Header, HTTPException
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

import config as app_config
from graph.graph import support_graph

app=FastAPI(title="AI Customer Support Agent",
            description="API for the Customer Support Agent",
            version="1.0.0")

class chatRequest(BaseModel):
    """
    Defines the JSON data that the client must send.

    Example:
    {
        "customer_id": "C002",
        "conversation_id": "conversation-001",
        "message": "Where is my order 10490?"
    }
    """
    customer_id: str = Field(
        min_length=1,
        description="Authenticated customer ID."
    )

    conversation_id: str = Field(
        min_length=1,
        description="Unique conversation/thread ID."
    )

    message: str = Field(
        min_length=1,
        description="Customer's message."
    )


class ChatResponse(BaseModel):
    """
    Standard response returned by our API.

    status is "completed" for a normal reply, or "pending_approval"
    when a refund is waiting for a support agent.
    order holds the latest order details shown in this turn (if any).
    """
    customer_id: str
    conversation_id: str
    response: str
    status: str = "completed"
    order: dict | None = None


class ApprovalRequest(BaseModel):
    decision: str = Field(
        description='"approved" or "rejected".'
    )


def message_text(message) -> str:
    """Gemini sometimes returns a list of content blocks instead of a string."""
    content = message.content

    if isinstance(content, list):
        return "".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and "text" in block
        )

    return str(content)


def latest_order(messages) -> dict | None:
    """
    Find order details from this turn's tool results so the UI
    can show them in the "Current Order" panel.
    """
    for message in reversed(messages):
        # Only look at the current turn.
        if isinstance(message, HumanMessage):
            break

        if isinstance(message, ToolMessage) and message.name == "get_order_status":
            try:
                data = json.loads(message.content)
            except (TypeError, ValueError):
                continue

            if data.get("found"):
                return {
                    "order_id": data.get("order_id"),
                    "status": data.get("status"),
                    "expected_delivery": data.get("expected_delivery"),
                }

    return None


def pending_approval_text(interrupt_value: dict) -> str:
    return (
        f"Your refund request for order {interrupt_value.get('order_id')} "
        f"(amount {interrupt_value.get('amount')}) is eligible and has been "
        "sent to our support team for approval. We'll update you here soon."
    )


def build_response(customer_id: str, conversation_id: str, result: dict) -> ChatResponse:
    """Turn a LangGraph result into our API response."""

    # The graph paused for human approval.
    if result.get("__interrupt__"):
        return ChatResponse(
            customer_id=customer_id,
            conversation_id=conversation_id,
            response=pending_approval_text(result["__interrupt__"][0].value),
            status="pending_approval",
        )

    messages = result["messages"]

    order = latest_order(messages)

    cancel_result = result.get("cancel_result")
    if order is None and cancel_result and cancel_result.get("success"):
        order = {
            "order_id": cancel_result.get("order_id"),
            "status": cancel_result.get("status"),
            "expected_delivery": None,
        }

    return ChatResponse(
        customer_id=customer_id,
        conversation_id=conversation_id,
        response=message_text(messages[-1]),
        order=order,
    )


def handle_graph_error(error: Exception):
    error_message = str(error)

    if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
        raise HTTPException(
            status_code=429,
            detail="AI service rate limit exceeded. Please try again later."
        )

    raise HTTPException(
        status_code=500,
        detail="Internal server error."
    )


@app.get("/")
def root():
    """
    Health-check endpoint.

    Returns a simple JSON object so we can verify
    that the API server is running.
    """
    return {
        "messages": "API is running successfully!"
    }

@app.post("/chat", response_model=ChatResponse)
def chat(request:chatRequest):
    """
    Send a customer message to the LangGraph agent.

    FastAPI receives the request,
    converts it into our SupportState,
    and starts the existing graph.
    """
    config={
        "configurable":{
            "thread_id":request.conversation_id
        }    }
    try:
        # If a refund in this conversation is still waiting for a
        # support agent, don't start a new run (it would lose the
        # pending approval). Just remind the customer.
        snapshot = support_graph.get_state(config)
        if snapshot.interrupts:
            return ChatResponse(
                customer_id=request.customer_id,
                conversation_id=request.conversation_id,
                response=(
                    "Your refund request is still waiting for approval "
                    "from our support team. I'll update you here as soon "
                    "as it's reviewed."
                ),
                status="pending_approval",
            )

        result = support_graph.invoke(
                {
                    "customer_id": request.customer_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": request.message,
                        }
                    ],
                },
                config=config,
            )

        return build_response(request.customer_id, request.conversation_id, result)

    except HTTPException:
        raise
    except Exception as e:
        handle_graph_error(e)


@app.post("/approvals/{conversation_id}", response_model=ChatResponse)
def decide_refund(
    conversation_id: str,
    request: ApprovalRequest,
    x_admin_key: str | None = Header(default=None),
):
    """
    Support staff approve or reject a pending refund.

    Requires the X-Admin-Key header to match ADMIN_API_KEY,
    so customers cannot approve their own refunds.
    """
    if not app_config.ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Refund approvals are disabled. Set ADMIN_API_KEY."
        )

    if not x_admin_key or not hmac.compare_digest(x_admin_key, app_config.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid admin key.")

    config = {"configurable": {"thread_id": conversation_id}}

    snapshot = support_graph.get_state(config)
    if not snapshot.interrupts:
        raise HTTPException(
            status_code=404,
            detail="No refund is waiting for approval in this conversation."
        )

    customer_id = snapshot.values.get("customer_id", "")

    try:
        result = support_graph.invoke(
            Command(resume=request.decision),
            config=config,
        )
        return build_response(customer_id, conversation_id, result)

    except HTTPException:
        raise
    except Exception as e:
        handle_graph_error(e)
