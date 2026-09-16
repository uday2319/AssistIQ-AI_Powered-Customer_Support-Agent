from graph.graph import support_graph
customer_message = input("Customer: ")
result = support_graph.invoke({
    "messages": [
        {
            "role": "user",
            "content": customer_message
        }
    ]
})

final_message = result["messages"][-1]

print("\n--- Support Response ---")
print(final_message.content)