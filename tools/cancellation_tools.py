from typing import Annotated

from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from db.queries import cancel_order as cancel_order_in_db


class CancellationInput(BaseModel):
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )


@tool(args_schema=CancellationInput)
def cancel_order(
    order_id: str,
    customer_id: Annotated[str, InjectedState("customer_id")]
) -> dict:
    """
    Cancel a customer order if its current status allows cancellation.
    """
    # The graph normally runs cancellation in cancel_order_node.
    # If this tool is ever called directly, it still uses the
    # trusted customer ID from graph state.
    return cancel_order_in_db(order_id, customer_id)
