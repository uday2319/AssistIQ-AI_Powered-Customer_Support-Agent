from langchain.tools import tool
from pydantic import BaseModel, Field

class CustomerInput(BaseModel):
    customer_id:str=Field(
    min_lenth=1,
    description="The customer's unique identifier.")

@tool(args_schema=CustomerInput)
def get_customer(customer_id: str) -> dict:
    """Get basic information about a customer using their customer ID."""
 
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
            "message": f"Customer {customer_id} was not found."
        }

    
    return {
        "success": True,
        "customer_id": customer_id,
        "name": customer["name"],
        "email": customer["email"]
    }

