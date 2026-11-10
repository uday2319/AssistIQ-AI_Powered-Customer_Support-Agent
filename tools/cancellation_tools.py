from langchain.tools import tool
from pydantic import BaseModel, Field

from db.queries import cancel_order as cancel_order_in_db


class CancellationInput(BaseModel): 
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )


@tool(args_schema=CancellationInput)
def cancel_order(order_id: str) -> dict:
    """
    Cancel a customer order if its current status allows cancellation.
    """
    result = cancel_order_in_db(order_id)


    return result