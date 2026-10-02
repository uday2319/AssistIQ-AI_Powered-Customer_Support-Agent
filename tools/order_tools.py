from typing import Annotated
from langchain.tools import tool
from pydantic import BaseModel, Field
from langgraph.prebuilt import InjectedState

from db.queries import find_order


class OrderStatusInput(BaseModel):
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )


@tool(args_schema=OrderStatusInput)
def get_order_status(
    order_id: str,
    customer_id: Annotated[str, InjectedState("customer_id")]
) -> dict:
    """
    Get the current status and expected delivery date
    of the authenticated customer's order.

    customer_id is injected by LangGraph from trusted state.
    Gemini cannot choose or modify it.
    """

    try:
        # The order ID comes from Gemini's tool request.
        # The customer ID comes from trusted graph state.
        order = find_order(
            order_id,
            customer_id
        )

        if order is None:
            return {
                "found": False,
                "message": "Order not found or not accessible."
            }

        return {
            "found": True,
            "order_id": order["order_id"],
            "status": order["status"],
            "expected_delivery": str(
                order["expected_delivery"]
            )
        }

    except Exception:
        # Don't expose internal database errors to the customer.
        return {
            "found": False,
            "error": "TOOL_ERROR",
            "message": "Unable to retrieve order status right now."
        }