from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from api.main import app


client = TestClient(app)


class FakeApprovalQueue:
    """In-memory stand-in for the refund_approvals table."""

    def __init__(self):
        self.rows = {}

    def add_pending(self, conversation_id, customer_id, order_id, payment_id, amount,
                    reason=None, reason_details=None):
        self.rows[conversation_id] = {
            "conversation_id": conversation_id, "customer_id": customer_id,
            "order_id": order_id, "payment_id": payment_id, "amount": amount,
            "reason": reason, "reason_details": reason_details,
            "requested_at": "2026-11-10T10:00:00", "status": "pending",
        }

    def list_pending(self):
        return [
            {k: v for k, v in row.items() if k != "status"}
            for row in self.rows.values() if row["status"] == "pending"
        ]

    def mark_decided(self, conversation_id, decision):
        self.rows[conversation_id]["status"] = decision


@pytest.fixture(autouse=True)
def approval_queue():
    """Tests never touch the real database."""
    queue = FakeApprovalQueue()
    with patch("api.main.approval_queries", queue):
        yield queue


def test_root():
    """Test the API health-check endpoint."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["messages"] == (
        "API is running successfully!"
    )


@patch("api.main.support_graph.invoke")
def test_chat_success(mock_invoke):
    """
    Test a successful /chat request.

    We mock LangGraph so this test does NOT call Gemini.
    """

    mock_invoke.return_value = {
        "messages": [
            AIMessage(content="Your order is currently processing.")
        ]
    }

    response = client.post(
        "/chat",
        json={
            "customer_id": "C002",
            "conversation_id": "conversation-001",
            "message": "Where is my order 10490?"
        },
    )

    assert response.status_code == 200

     
    assert response.json()["response"] == (
        "Your order is currently processing."
    )

    mock_invoke.assert_called_once()

# ------------------------------------------------------------------
# Refund approval through the API
# ------------------------------------------------------------------

import json
import uuid

from langchain_core.messages import HumanMessage, ToolMessage

import config as app_config
from api.main import latest_order
from graph import nodes

ELIGIBLE = {
    "eligible": True,
    "order_id": "10483",
    "payment_id": "P1",
    "amount": 499.0,
    "message": "Order is eligible for a refund.",
}


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, messages):
        return self.responses.pop(0)


def refund_tool_call():
    return AIMessage(
        content="",
        tool_calls=[{"name": "request_refund", "args": {"order_id": "10483", "reason": "damaged", "reason_details": "box crushed"}, "id": "c1"}],
    )


@patch.object(app_config, "ADMIN_API_KEY", "secret")
@patch.object(nodes, "execute_refund", return_value={"amount": 499.0, "message": "ok"})
@patch.object(nodes, "check_refund_eligibility", return_value=ELIGIBLE)
def test_refund_waits_for_admin_approval(mock_check, mock_execute):
    conversation_id = str(uuid.uuid4())
    body = {"customer_id": "C001", "conversation_id": conversation_id, "message": "Refund 10483"}

    with patch.object(nodes, "llm_with_tools", FakeLLM([refund_tool_call()])):
        # 1. Customer asks: the agent checks the reason with them first.
        response = client.post("/chat", json=body)
        assert response.status_code == 200
        assert response.json()["status"] == "awaiting_confirmation"
        assert "damaged" in response.json()["response"]

        # Customer confirms: the reply explains it's waiting for approval.
        response = client.post("/chat", json={**body, "message": "yes"})
        assert response.json()["status"] == "pending_approval"
        assert "10483" in response.json()["response"]

        # 2. Another customer message while waiting: still pending, no crash.
        response = client.post("/chat", json={**body, "message": "any update?"})
        assert response.json()["status"] == "pending_approval"

        # 3. Wrong or missing admin key is refused.
        url = f"/approvals/{conversation_id}"
        assert client.post(url, json={"decision": "approved"}).status_code == 401
        assert client.post(
            url, json={"decision": "approved"}, headers={"X-Admin-Key": "wrong"}
        ).status_code == 401
        mock_execute.assert_not_called()

        # 4. Staff approves with the right key: refund is executed.
        response = client.post(
            url, json={"decision": "approved"}, headers={"X-Admin-Key": "secret"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "processed" in response.json()["response"]
    mock_execute.assert_called_once()

    # 5. Nothing left to approve.
    response = client.post(
        f"/approvals/{conversation_id}",
        json={"decision": "approved"},
        headers={"X-Admin-Key": "secret"},
    )
    assert response.status_code == 404


@patch.object(app_config, "ADMIN_API_KEY", None)
def test_approvals_disabled_without_admin_key():
    response = client.post(
        "/approvals/anything",
        json={"decision": "approved"},
        headers={"X-Admin-Key": "x"},
    )
    assert response.status_code == 503


def test_latest_order_reads_current_turn_only():
    order_json = json.dumps({
        "found": True, "order_id": "10490",
        "status": "processing", "expected_delivery": "2026-11-12",
    })
    old_turn = [
        HumanMessage(content="where is 10490"),
        ToolMessage(content=order_json, name="get_order_status", tool_call_id="a"),
        AIMessage(content="It's processing."),
    ]

    # Order found in this turn.
    assert latest_order(old_turn)["status"] == "processing"

    # A new turn with no order lookup should not reuse the old order.
    assert latest_order(old_turn + [HumanMessage(content="thanks"), AIMessage(content="np")]) is None


@patch.object(nodes, "cancel_order_in_db")
@patch.object(nodes, "find_order", return_value={"order_id": "10490", "status": "pending"})
def test_cancel_confirmation_through_chat(mock_find, mock_cancel):
    mock_cancel.return_value = {
        "success": True, "order_id": "10490", "status": "cancelled", "message": "ok",
    }
    cancel_call = AIMessage(
        content="",
        tool_calls=[{"name": "cancel_order", "args": {"order_id": "10490"}, "id": "c1"}],
    )
    body = {"customer_id": "C002", "conversation_id": str(uuid.uuid4()), "message": "Cancel 10490"}

    with patch.object(nodes, "llm_with_tools", FakeLLM([cancel_call])):
        response = client.post("/chat", json=body)
        assert response.json()["status"] == "awaiting_confirmation"
        assert "Are you sure" in response.json()["response"]
        mock_cancel.assert_not_called()

        # The customer's next message is the answer.
        response = client.post("/chat", json={**body, "message": "yes"})

    assert response.json()["status"] == "completed"
    assert response.json()["order"]["status"] == "cancelled"
    mock_cancel.assert_called_once_with(order_id="10490", customer_id="C002")


@patch.object(app_config, "ADMIN_API_KEY", "secret")
@patch.object(nodes, "execute_refund", return_value={"amount": 499.0, "message": "ok"})
@patch.object(nodes, "check_refund_eligibility", return_value=ELIGIBLE)
def test_staff_queue_and_customer_update(mock_check, mock_execute, approval_queue):
    conversation_id = str(uuid.uuid4())
    staff = {"X-Admin-Key": "secret"}

    with patch.object(nodes, "llm_with_tools", FakeLLM([refund_tool_call()])):
        body = {"customer_id": "C001", "conversation_id": conversation_id, "message": "Refund 10483"}
        client.post("/chat", json=body)
        # Nothing reaches staff until the customer confirms the reason.
        assert client.get("/approvals", headers=staff).json()["pending"] == []
        client.post("/chat", json={**body, "message": "yes"})

    # Staff list needs the key.
    assert client.get("/approvals").status_code == 401

    # Staff see the refund with the customer's message.
    pending = client.get("/approvals", headers=staff).json()["pending"]
    assert len(pending) == 1
    assert pending[0]["order_id"] == "10483"
    assert pending[0]["amount"] == 499.0
    assert pending[0]["reason"] == "damaged"
    assert pending[0]["reason_details"] == "box crushed"
    assert {"role": "customer", "content": "Refund 10483"} in pending[0]["transcript"]

    # Customer checks for updates: still waiting.
    url = f"/conversations/{conversation_id}?customer_id=C001"
    assert client.get(url).json()["status"] == "pending_approval"

    # Staff reject it.
    client.post(f"/approvals/{conversation_id}", json={"decision": "reject"}, headers=staff)
    assert approval_queue.rows[conversation_id]["status"] == "rejected"
    assert client.get("/approvals", headers=staff).json()["pending"] == []
    mock_execute.assert_not_called()

    # Customer checks again and sees the decision.
    update = client.get(url).json()
    assert update["status"] == "completed"
    assert "not approved" in update["response"]


def test_other_customer_cannot_use_conversation():
    conversation_id = str(uuid.uuid4())
    body = {"customer_id": "C001", "conversation_id": conversation_id, "message": "hi"}

    with patch.object(nodes, "llm_with_tools", FakeLLM([AIMessage(content="Hello!")])):
        assert client.post("/chat", json=body).status_code == 200

    # Someone else using the same conversation ID is refused.
    assert client.post("/chat", json={**body, "customer_id": "C002"}).status_code == 404
    assert client.get(f"/conversations/{conversation_id}?customer_id=C002").status_code == 404
