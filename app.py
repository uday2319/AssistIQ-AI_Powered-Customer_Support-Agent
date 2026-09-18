from graph.graph import support_graph
from langgraph.types import Command

customer_message = input("Customer: ")
config = {
    "configurable": {
        "thread_id": "test-refund-002"
    }
}

result = support_graph.invoke({
    "messages": [
        {
            "role": "user",
            "content": customer_message
        }
    ]
    
} ,
config=config 
)

print("\n--- Graph paused ---")
print(result["__interrupt__"])

approval = "rejected"


result = support_graph.invoke(
    Command(resume=approval),
    config=config
)


print("\n--- Final Result ---")
print(result)