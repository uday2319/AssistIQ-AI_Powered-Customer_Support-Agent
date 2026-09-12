from langchain.tools import tool
from pydantic import BaseModel,Field

class OrderStatusInput(BaseModel):
    order_id: str = Field(
        min_length=1,
        description="The customer's order ID."
    )

 
@tool(args_schema=OrderStatusInput)
def get_order_status(order_id: str) -> dict:
    """Get the current status and expected delivery date of a customer order."""
    orders = {
    "10482": {
        "status": "shipped",
        "expected_delivery": "tomorrow"
    },
    "10483": {
        "status": "delivered",
        "expected_delivery": "delivered yesterday"
    },
    "10484": {
        "status": "cancelled",
        "expected_delivery": None
    }
}

    try:
        order=orders.get(order_id)
        if order is None:
            return {"found":False,"message":f"Order {order_id} was not found"}
        
        return {
                "found": True,
                "order_id": order_id,
                "status": order["status"],
                "expected_delivery": order["expected_delivery"]
            }

    except Exception as e:

        return {
            "found":False,
            "error":"TOOL_ERROR",
            "message":" Unable to retrieve order status Now. Please try again later.",
        }

  
           
         
     