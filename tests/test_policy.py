"""
policy.yaml is the single source of truth.
These tests make sure the documents and the code follow it.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

import db.queries
import utils.refund_policy
from tools import refund_tools
from tools.refund_tools import check_refund_eligibility, request_refund
from utils.policy import (
    ALLOWED_REFUND_REASONS,
    CANCELLABLE_STATUSES,
    KNOWLEDGE_BASE_DIR,
    REFUND_WINDOW_DAYS,
    RULES,
    policy_documents,
)


def test_documents_match_policy_file():
    """
    Fails if someone edits a knowledge-base file by hand, or edits
    policy.yaml without regenerating. Fix: python -m utils.policy
    """
    for name, expected in policy_documents().items():
        on_disk = (KNOWLEDGE_BASE_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert on_disk == expected, f"{name} is out of date. Run: python -m utils.policy"


def test_code_uses_policy_values():
    assert db.queries.CANCELLABLE_STATUSES == CANCELLABLE_STATUSES

    today = date.today()
    assert utils.refund_policy.is_refund_eligible(today - timedelta(days=REFUND_WINDOW_DAYS))
    assert not utils.refund_policy.is_refund_eligible(today - timedelta(days=REFUND_WINDOW_DAYS + 1))

    # Changing the window in the policy changes what the code allows.
    with patch.object(utils.refund_policy, "REFUND_WINDOW_DAYS", 30):
        assert utils.refund_policy.is_refund_eligible(today - timedelta(days=20))


def test_refund_tool_offers_exactly_the_policy_reasons():
    schema = request_refund.tool_call_schema.model_json_schema()
    offered = schema["properties"]["reason"]["enum"]
    assert offered == list(ALLOWED_REFUND_REASONS) + ["other"]
    assert set(schema["required"]) == {"order_id", "reason", "reason_details"}


# ------------------------------------------------------------------
# Eligibility: every refusal quotes the policy rule
# ------------------------------------------------------------------

def fake_order(delivered_days_ago):
    delivered = None if delivered_days_ago is None else date.today() - timedelta(days=delivered_days_ago)
    return {"order_id": "1", "customer_id": "C001", "status": "delivered", "delivered_at": delivered}


PAID = {"payment_id": "P1", "order_id": "1", "amount": 100.0, "payment_status": "paid"}


@pytest.fixture
def db_fakes():
    with patch.object(refund_tools, "find_order") as find_order, \
         patch.object(refund_tools, "find_payment", return_value=PAID), \
         patch.object(refund_tools, "find_refund", return_value=None):
        yield find_order


def test_other_reason_is_refused_with_the_rule(db_fakes):
    result = check_refund_eligibility("1", "C001", "other")

    assert result["eligible"] is False
    assert result["error"] == "REASON_NOT_ALLOWED"
    assert result["message"] == RULES["refund_reasons"]
    # Refused before touching the database.
    db_fakes.assert_not_called()


@pytest.mark.parametrize("reason", list(ALLOWED_REFUND_REASONS))
def test_allowed_reasons_pass(db_fakes, reason):
    db_fakes.return_value = fake_order(delivered_days_ago=1)
    assert check_refund_eligibility("1", "C001", reason)["eligible"] is True


def test_not_delivered_gets_the_right_message(db_fakes):
    db_fakes.return_value = fake_order(delivered_days_ago=None)
    result = check_refund_eligibility("1", "C001", "damaged")

    assert result["error"] == "NOT_DELIVERED"
    assert RULES["refund_delivered_only"] in result["message"]


def test_window_refusal_quotes_the_rule(db_fakes):
    db_fakes.return_value = fake_order(delivered_days_ago=REFUND_WINDOW_DAYS + 5)
    result = check_refund_eligibility("1", "C001", "damaged")

    assert result["error"] == "REFUND_WINDOW_EXPIRED"
    assert RULES["refund_window"] in result["message"]
