import hmac
import json

from fastapi import Depends, FastAPI, Header, HTTPException
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

import config as app_config
from db import approval_queries
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

    status is one of:
    - "completed": a normal reply
    - "pending_approval": a refund is waiting for a support agent
    - "awaiting_confirmation": the agent asked the customer to confirm
      a cancellation (the next message is treated as yes/no)
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

    # The graph paused and is waiting for someone.
    if result.get("__interrupt__"):
        value = result["__interrupt__"][0].value

        # Waiting for the customer to confirm a cancellation.
        if value.get("type") == "cancel_confirmation":
            return ChatResponse(
                customer_id=customer_id,
                conversation_id=conversation_id,
                response=value["message"],
                status="awaiting_confirmation",
            )

        # Waiting for a support agent to approve a refund.
        return ChatResponse(
            customer_id=customer_id,
            conversation_id=conversation_id,
            response=pending_approval_text(value),
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

def require_admin(x_admin_key: str | None = Header(default=None)):
    """
    Only support staff may see or decide refunds.
    The X-Admin-Key header must match ADMIN_API_KEY.
    """
    if not app_config.ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Refund approvals are disabled. Set ADMIN_API_KEY."
        )

    if not x_admin_key or not hmac.compare_digest(x_admin_key, app_config.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid admin key.")


def pending_interrupt(snapshot) -> dict | None:
    """The value the graph paused with, or None if it isn't paused."""
    if snapshot.interrupts:
        return snapshot.interrupts[0].value
    return None


def queue_refund_for_staff(conversation_id: str, customer_id: str, value: dict):
    """Add a paused refund to the staff approval queue (safe to repeat)."""
    approval_queries.add_pending(
        conversation_id=conversation_id,
        customer_id=customer_id,
        order_id=value["order_id"],
        payment_id=value["payment_id"],
        amount=value["amount"],
    )


def transcript(messages) -> list[dict]:
    """Customer and agent messages only (no tool calls), for staff to read."""
    lines = []
    for message in messages:
        if message.type not in ("human", "ai"):
            continue
        text = message_text(message).strip()
        if text:
            role = "customer" if message.type == "human" else "agent"
            lines.append({"role": role, "content": text})
    return lines


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
        snapshot = support_graph.get_state(config)

        # A conversation belongs to one customer. Don't let another
        # customer ID continue it.
        owner = snapshot.values.get("customer_id")
        if owner and owner != request.customer_id:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        waiting_for = pending_interrupt(snapshot)

        # The agent asked "are you sure you want to cancel?".
        # This message is the customer's answer, so resume with it.
        if waiting_for and waiting_for.get("type") == "cancel_confirmation":
            result = support_graph.invoke(
                Command(resume=request.message),
                config=config,
            )

        # If a refund in this conversation is still waiting for a
        # support agent, don't start a new run (it would lose the
        # pending approval). Just remind the customer.
        elif waiting_for:
            # Make sure staff can see it (fixes it if saving failed before).
            queue_refund_for_staff(request.conversation_id, request.customer_id, waiting_for)
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

        else:
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

        response = build_response(request.customer_id, request.conversation_id, result)

        # A new refund is waiting: put it in the staff queue.
        if response.status == "pending_approval":
            queue_refund_for_staff(
                request.conversation_id,
                request.customer_id,
                result["__interrupt__"][0].value,
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        handle_graph_error(e)


@app.get("/conversations/{conversation_id}", response_model=ChatResponse)
def conversation_status(conversation_id: str, customer_id: str):
    """
    Let the customer check for updates, for example after staff
    approve or reject their refund.
    """
    snapshot = support_graph.get_state({"configurable": {"thread_id": conversation_id}})

    if snapshot.values.get("customer_id") != customer_id:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    waiting_for = pending_interrupt(snapshot)
    messages = snapshot.values.get("messages", [])

    if waiting_for and waiting_for.get("type") == "refund_approval":
        status, text = "pending_approval", pending_approval_text(waiting_for)
    elif waiting_for:
        status, text = "awaiting_confirmation", waiting_for["message"]
    else:
        status, text = "completed", message_text(messages[-1]) if messages else ""

    return ChatResponse(
        customer_id=customer_id,
        conversation_id=conversation_id,
        response=text,
        status=status,
    )


@app.get("/approvals", dependencies=[Depends(require_admin)])
def list_approvals():
    """
    Staff only: every refund waiting for a decision,
    with the chat so far so staff can understand the request.
    """
    items = []

    for item in approval_queries.list_pending():
        snapshot = support_graph.get_state(
            {"configurable": {"thread_id": item["conversation_id"]}}
        )
        item["transcript"] = transcript(snapshot.values.get("messages", []))
        items.append(item)

    return {"pending": items}


@app.post(
    "/approvals/{conversation_id}",
    response_model=ChatResponse,
    dependencies=[Depends(require_admin)],
)
def decide_refund(conversation_id: str, request: ApprovalRequest):
    """
    Support staff approve or reject a pending refund.

    Requires the X-Admin-Key header to match ADMIN_API_KEY,
    so customers cannot approve their own refunds.
    """
    config = {"configurable": {"thread_id": conversation_id}}

    snapshot = support_graph.get_state(config)
    waiting_for = pending_interrupt(snapshot)
    if not waiting_for or waiting_for.get("type") != "refund_approval":
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

        # Record the final decision the graph actually made.
        decision = support_graph.get_state(config).values.get("human_approval", "rejected")
        approval_queries.mark_decided(conversation_id, decision)

        return build_response(customer_id, conversation_id, result)

    except HTTPException:
        raise
    except Exception as e:
        handle_graph_error(e)
