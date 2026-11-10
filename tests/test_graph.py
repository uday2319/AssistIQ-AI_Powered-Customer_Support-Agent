"""
Tests for the LangGraph workflow.

Gemini and the database are replaced with fakes, so these tests
are fast, free, and do not need a network connection.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from graph import nodes
from graph.graph import support_graph
from utils.refund_policy import is_refund_eligible


class FakeLLM:
    """Returns pre-written AI messages one by one and records what it was sent."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


def tool_call_message(name, args, call_id="call-1"):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id}],
    )


def new_config():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def start(config, text="hi", customer_id="C001"):
    return support_graph.invoke(
        {
            "customer_id": customer_id,
            "messages": [{"role": "user", "content": text}],
        },
        config=config,
    )


def assert_every_tool_call_answered(messages):
    """Every tool call from the AI must have a matching ToolMessage."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                assert tool_call["id"] in answered


REFUND_ARGS = {"order_id": "10483", "reason": "damaged", "reason_details": "screen cracked"}

ELIGIBLE = {
    "eligible": True,
    "order_id": "10483",
    "payment_id": "P1",
    "amount": 499.0,
    "message": "Order is eligible for a refund.",
}


# ------------------------------------------------------------------
# Refund workflow
# ------------------------------------------------------------------

@patch.object(nodes, "execute_refund")
@patch.object(nodes, "check_refund_eligibility", return_value=ELIGIBLE)
def test_refund_pauses_then_runs_after_approval(mock_check, mock_execute):
    mock_execute.return_value = {"amount": 499.0, "message": "ok"}
    fake = FakeLLM([tool_call_message("request_refund", REFUND_ARGS)])
    config = new_config()

    with patch.object(nodes, "llm_with_tools", fake):
        result = start(config, "Refund order 10483 please")

        # The graph must pause and wait for a human.
        assert "__interrupt__" in result
        mock_check.assert_called_once_with("10483", "C001", "damaged")
        mock_execute.assert_not_called()

        # Different spellings of "approve" should all work.
        result = support_graph.invoke(Command(resume="Accepted"), config=config)

    mock_execute.assert_called_once_with(payment_id="P1", amount=499.0)
    assert "processed" in result["messages"][-1].content
    assert_every_tool_call_answered(result["messages"])


@patch.object(nodes, "execute_refund")
@patch.object(nodes, "check_refund_eligibility", return_value=ELIGIBLE)
def test_refund_rejected_does_not_move_money(mock_check, mock_execute):
    fake = FakeLLM([tool_call_message("request_refund", REFUND_ARGS)])
    config = new_config()

    with patch.object(nodes, "llm_with_tools", fake):
        start(config, "Refund order 10483")
        result = support_graph.invoke(Command(resume="rejected"), config=config)

    mock_execute.assert_not_called()
    assert "not approved" in result["messages"][-1].content


@patch.object(nodes, "check_refund_eligibility")
def test_ineligible_refund_tells_customer_why(mock_check):
    mock_check.return_value = {
        "eligible": False,
        "error": "REFUND_WINDOW_EXPIRED",
        "message": "Order 10483 is outside the 7-day refund window.",
    }
    fake = FakeLLM([tool_call_message("request_refund", REFUND_ARGS)])

    with patch.object(nodes, "llm_with_tools", fake):
        result = start(new_config(), "Refund order 10483")

    assert "__interrupt__" not in result
    assert "7-day refund window" in result["messages"][-1].content
    assert_every_tool_call_answered(result["messages"])


# ------------------------------------------------------------------
# Cancellation workflow
# ------------------------------------------------------------------

PROCESSING_ORDER = {"order_id": "10490", "customer_id": "C002", "status": "processing"}


@patch.object(nodes, "cancel_order_in_db")
@patch.object(nodes, "find_order", return_value=PROCESSING_ORDER)
def test_cancel_asks_for_confirmation_then_cancels(mock_find, mock_cancel):
    mock_cancel.return_value = {"success": True, "message": "Order cancelled successfully."}
    fake = FakeLLM([
        tool_call_message("cancel_order", {"order_id": "10490"}),
        AIMessage(content="Anything else I can help with?"),
    ])
    config = new_config()

    with patch.object(nodes, "llm_with_tools", fake):
        result = start(config, "Cancel order 10490", customer_id="C002")

        # Nothing is cancelled until the customer confirms.
        assert result["__interrupt__"][0].value["type"] == "cancel_confirmation"
        mock_find.assert_called_with("10490", "C002")
        mock_cancel.assert_not_called()

        result = support_graph.invoke(Command(resume="Yes please"), config=config)

        mock_cancel.assert_called_once_with(order_id="10490", customer_id="C002")
        assert "cancelled" in result["messages"][-1].content

        # A follow-up message in the same conversation must work.
        # Before the fix, the history had a tool call with no reply.
        result = start(config, "thanks", customer_id="C002")

    assert result["messages"][-1].content == "Anything else I can help with?"
    assert_every_tool_call_answered(fake.calls[-1])


@patch.object(nodes, "cancel_order_in_db")
@patch.object(nodes, "find_order", return_value=PROCESSING_ORDER)
def test_cancel_kept_when_customer_says_no(mock_find, mock_cancel):
    fake = FakeLLM([tool_call_message("cancel_order", {"order_id": "10490"})])
    config = new_config()

    with patch.object(nodes, "llm_with_tools", fake):
        start(config, "Cancel order 10490", customer_id="C002")
        result = support_graph.invoke(Command(resume="no, keep it"), config=config)

    mock_cancel.assert_not_called()
    assert "haven't cancelled" in result["messages"][-1].content


@patch.object(nodes, "cancel_order_in_db")
@patch.object(nodes, "find_order")
def test_cancel_skips_question_when_order_cannot_be_cancelled(mock_find, mock_cancel):
    fake = FakeLLM([
        tool_call_message("cancel_order", {"order_id": "10482"}),
        tool_call_message("cancel_order", {"order_id": "99999"}),
    ])

    with patch.object(nodes, "llm_with_tools", fake):
        # Already shipped: explain, don't ask "are you sure?".
        mock_find.return_value = {"order_id": "10482", "status": "shipped"}
        result = start(new_config(), "Cancel order 10482")
        assert "__interrupt__" not in result
        assert "already shipped" in result["messages"][-1].content

        # Not found / someone else's order: same safe message.
        mock_find.return_value = None
        result = start(new_config(), "Cancel order 99999")
        assert "couldn't find order 99999" in result["messages"][-1].content

    mock_cancel.assert_not_called()


def test_is_yes():
    for answer in ["yes", "Yes please", "ok, cancel it", "Y", "confirm"]:
        assert nodes.is_yes(answer), answer
    for answer in ["no", "yes but wait", "not now", "what's the status?", "", None]:
        assert not nodes.is_yes(answer), answer


# ------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------

def test_system_prompt_is_sent_to_llm():
    fake = FakeLLM([AIMessage(content="Hello!")])

    with patch.object(nodes, "llm_with_tools", fake):
        start(new_config(), "hi")

    first_message = fake.calls[0][0]
    assert first_message.type == "system"
    assert date.today().isoformat() in first_message.content


def test_normalize_decision():
    assert nodes.normalize_decision("Approved") == "approved"
    assert nodes.normalize_decision(" accepted ") == "approved"
    assert nodes.normalize_decision("no") == "rejected"
    assert nodes.normalize_decision(None) == "rejected"


def test_refund_window():
    today = date.today()
    assert is_refund_eligible(today)
    assert is_refund_eligible(today - timedelta(days=7))
    assert not is_refund_eligible(today - timedelta(days=8))
    assert not is_refund_eligible(None)
