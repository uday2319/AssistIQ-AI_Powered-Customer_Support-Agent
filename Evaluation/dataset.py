
evaluation_cases = [
    {
        "input": "What is your refund policy?",
        "customer_id": "C001",
        "expected": {
            "type": "knowledge",
            "should_use_rag": True,
        },
    },
 

    {
        "input": "Where is my order 10483?",
        "customer_id": "C002",
        "expected": {
            "type": "authorization",
            "order_id": "10483",
            "should_find_order": False,
        },
    },
]
if __name__ == "__main__":

    print(f"Total evaluation cases: {len(evaluation_cases)}")

    for case in evaluation_cases:
        print(case["input"])