from graph.graph import support_graph
from langgraph.types import Command

customer_message = input("Customer: ")
config = {
    "configurable": {
        "thread_id": "test-refund-002"
    },
     "metadata": {
        "customer_id": "C001",
        "workflow": "customer_support",
        "environment": "development",
        "version": "v0.9"
    },
    "tags": [
        "customer-support",
        "v0.9",
        "development"
    ]
}

result = support_graph.invoke({
    "customer_id": "C001",
    "messages": [
        {
            "role": "user",
            "content": customer_message
        }
    ]
    
} ,
config=config 
)
print("\n--- Graph Result ---")
print(result)

if "__interrupt__" in result:
    print("\n--- Graph paused ---")
    print(result["__interrupt__"])

approval = "Accepted"


result = support_graph.invoke(
    Command(resume=approval),
    config=config
)


print("\n--- Final Result ---")
print(result)