from typing import Annotated

from langchain.tools import tool
from langgraph.prebuilt import InjectedState


@tool
def get_customer(
    customer_id: Annotated[str, InjectedState("customer_id")]
) -> dict:
    """Get basic information (name, email) about the current customer."""

    # customer_id is injected by LangGraph from trusted state.
    # Gemini cannot choose it, so it cannot look up other customers.
    customers = {
        "C001": {
            "name": "Uday",
            "email": "uday@example.com"
        },
        "C002": {
            "name": "Rahul",
            "email": "rahul@example.com"
        }
    }

    customer = customers.get(customer_id)

    if customer is None:
        return {
            "success": False,
            "error": "CUSTOMER_NOT_FOUND",
            "message": "Customer was not found."
        }

    return {
        "success": True,
        "customer_id": customer_id,
        "name": customer["name"],
        "email": customer["email"]
    }
