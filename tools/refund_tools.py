from langchain.tools import tool
from pydantic import BaseModel, Field

from db.queries import find_order
from db.payment_queries import find_payment
from db.refund_queries import find_refund, create_refund
from utils.refund_policy import is_refund_eligible
class RefundInput(BaseModel):
    
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )


def check_refund_eligibility(order_id:str)->dict:
    """
    Check whether an order can be refunded.

    IMPORTANT:
    This function only checks the refund conditions.
    It does NOT create a refund.
    """
    order=find_order(order_id)
    if order is None:
        return {
            "eligible":False,
            "error":"ORDER_NOT_FUND",
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
            "message": f"Order {order_id} has already been refunded."
        }

    
    if payment["payment_status"] != "paid":
        return {
            "eligible": False,
            "error": "PAYMENT_NOT_ELIGIBLE",
            "message": "This payment is not eligible for a refund."
        }

    
    if not is_refund_eligible(order["delivered_at"]):
        return {
            "eligible": False,
            "error": "REFUND_WINDOW_EXPIRED",
            "message": f"Order {order_id} is outside the 7-day refund window."
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

class RefundRequestInput(BaseModel):
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )


@tool(args_schema=RefundRequestInput)
def request_refund(order_id: str) -> dict:
    """
    Request a refund for an order.

    This tool does NOT process the refund.
    It only tells the workflow that a refund has been requested.
    """
    return {
        "refund_requested": True,
        "order_id": order_id
    }