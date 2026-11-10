from langchain.tools import tool
from pydantic import BaseModel, Field
from db.queries import find_order
from db.payment_queries import find_payment
from db.refund_queries import find_refund, create_refund
from typing import Literal

from utils.policy import (
    ALLOWED_REFUND_REASONS,
    REFUNDABLE_PAYMENT_STATUSES,
    REFUND_WINDOW_DAYS,
    RULES,
)
from utils.refund_policy import is_refund_eligible

class RefundInput(BaseModel):
    
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )


def check_refund_eligibility(order_id: str, customer_id: str, reason: str) -> dict:
    """
    Perform all backend checks before a refund can proceed.
    Every rule comes from policy.yaml, and every refusal quotes
    the same rule sentence the customer can read in the policy.

    customer_id comes from trusted application state,
    so Gemini cannot choose whose order is being accessed.
    """

    # The reason must be one the policy allows.
    if reason not in ALLOWED_REFUND_REASONS:
        return {
            "eligible": False,
            "error": "REASON_NOT_ALLOWED",
            "message": RULES["refund_reasons"],
        }

    order=find_order(order_id,customer_id)
    if order is None:
        return {
            "eligible":False,
            "error":"ORDER_NOT_FOUND",
            "message":f"Order {order_id} was not found."}
    
    payment=find_payment(order_id)

    if payment is None:
        return {
            "eligible": False,
            "error": "PAYMENT_NOT_FOUND",
            "message": f"No payment was found for order {order_id}."
        }

    
    existing_refund = find_refund(payment["payment_id"])

    if existing_refund is not None:
        return {
            "eligible": False,
            "error": "ALREADY_REFUNDED",
            "message": f"Order {order_id} has already been refunded. {RULES['refund_once']}"
        }

    if payment["payment_status"] not in REFUNDABLE_PAYMENT_STATUSES:
        return {
            "eligible": False,
            "error": "PAYMENT_NOT_ELIGIBLE",
            "message": RULES["refund_paid_only"],
        }

    # Not delivered yet (before, this wrongly said "outside the window").
    if order["delivered_at"] is None:
        return {
            "eligible": False,
            "error": "NOT_DELIVERED",
            "message": f"Order {order_id} hasn't been delivered yet. {RULES['refund_delivered_only']}"
        }

    if not is_refund_eligible(order["delivered_at"]):
        return {
            "eligible": False,
            "error": "REFUND_WINDOW_EXPIRED",
            "message": (
                f"Order {order_id} is outside the {REFUND_WINDOW_DAYS}-day refund window. "
                f"{RULES['refund_window']}"
            ),
        }


    return {
        "eligible": True,
        "order_id": order_id,
        "payment_id": payment["payment_id"],
        "amount": payment["amount"],
        "message": "Order is eligible for a refund."
    }



@tool(args_schema=RefundInput)
def refund_order(order_id:str)->dict:
    """
    Execute a refund after the order has already been approved.

    This function performs the financial action.
    Eligibility and human approval are handled elsewhere.
    """
    
    return {
        "success": False,
        "error": "NOT_READY",
        "message": "Refund execution will be connected to the approval workflow."
    }

from db.refund_queries import create_refund


def execute_refund(payment_id: str, amount: float) -> dict:
    """
    Actually create the refund in PostgreSQL.

    This function is intentionally NOT an LLM tool.
    LangGraph will call it only after human approval.
    """


    refund_id = f"R-{payment_id}"
    refund = create_refund(
        refund_id=refund_id,
        payment_id=payment_id,
        amount=amount
    )

    # Return the result to the workflow.
    return {
        "success": True,
        "refund_id": refund["refund_id"],
        "payment_id": refund["payment_id"],
        "amount": refund["amount"],
        "refund_status": refund["refund_status"],
        "message": "Refund processed successfully."
    }

# The reasons the agent can choose: the allowed ones from policy.yaml,
# plus "other". The agent only classifies; the code decides, and
# "other" is always refused.
RefundReason = Literal[tuple(ALLOWED_REFUND_REASONS) + ("other",)]


class RefundRequestInput(BaseModel):
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )

    reason: RefundReason = Field(
        description=(
            "Why the customer wants a refund, based ONLY on what the customer said. "
            + "; ".join(f"'{code}' = {meaning}" for code, meaning in ALLOWED_REFUND_REASONS.items())
            + "; 'other' = any other reason (changed mind, found it cheaper, no longer needed, ...). "
            "Never pick a reason the customer did not give."
        )
    )

    reason_details: str = Field(
        min_length=1,
        description="The customer's own words describing the problem.",
    )


@tool(args_schema=RefundRequestInput)
def request_refund(order_id: str, reason: str, reason_details: str) -> dict:
    """
    Request a refund for an order.

    Only call this after the customer has said WHY they want the refund.
    If they haven't, ask them first.

    This tool does NOT process the refund. The system checks the
    refund policy, and support staff must approve it.
    """
    return {
        "refund_requested": True,
        "order_id": order_id,
        "reason": reason,
    }