from graph.graph import support_graph
from Evaluation.dataset import evaluation_cases
from langgraph.types import Command
from Evaluation.tool_evaluator import evaluate_tool_selection

def run_case(case: dict):
    """
    Run one evaluation case through the real support graph.

    Why:
    We want to evaluate the actual application, not a separate
    test implementation.
    """

    config = {
        "configurable": {
            "thread_id": f"eval-{case['expected']['type']}-{case['expected'].get('order_id', 'general')}"
        },

    
        "metadata": {
            "evaluation": True,
            "test_type": case["expected"]["type"],
            "customer_id": case["customer_id"],
            "version": "v0.9",
        },

        "tags": [
            "evaluation",
            "v0.9",
        ],
    }

    result = support_graph.invoke(
        {
            "customer_id": case["customer_id"],
            "messages": [
                {
                    "role": "user",
                    "content": case["input"],
                }
            ],
        },
        config=config,
    )
 
    if "__interrupt__" in result:
        result = support_graph.invoke(
            Command(resume="approved"),
            config=config,
        )

    return result


if __name__ == "__main__":

    print("Running evaluation...\n")

    for index, case in enumerate(evaluation_cases, start=1):

        print(f"Test {index}/{len(evaluation_cases)}")
        print(f"Input: {case['input']}")

        try:
            result = run_case(case)
            tool_status = evaluate_tool_selection(case, result)

            print(f"Tool selection: {tool_status}")
            final_message = result["messages"][-1]

            print(f"Result: {final_message.content}")
            print("Status: COMPLETED")

        except Exception as e:
            print(f"Status: FAILED")
            print(f"Error: {e}")

        print("-" * 60)