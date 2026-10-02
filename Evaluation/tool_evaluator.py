def evaluate_tool_selection(case: dict, result: dict) -> str:
    """
    Check whether the agent used the expected tool/workflow.

    We inspect the messages produced by LangGraph rather than
    asking another LLM to judge the result.
    """

    expected_type = case["expected"]["type"]

    # ---------------------------------------------------------
    # ORDER STATUS
    # ---------------------------------------------------------
    if expected_type == "order_status":
        expected_tool = "get_order_status"

    # ---------------------------------------------------------
    # CANCELLATION
    # ---------------------------------------------------------
    elif expected_type == "cancellation":
        expected_tool = "cancel_order"

    # ---------------------------------------------------------
    # REFUND
    # ---------------------------------------------------------
    elif expected_type == "refund":
        expected_tool = "request_refund"

    # ---------------------------------------------------------
    # RAG / KNOWLEDGE
    # ---------------------------------------------------------
    elif expected_type == "knowledge":
        expected_tool = "search_knowledge_base"

    # ---------------------------------------------------------
    # AUTHORIZATION
    # ---------------------------------------------------------
    elif expected_type == "authorization":
        expected_tool = "get_order_status"

    else:
        return "FAIL"

    for message in result["messages"]:
        tool_name = getattr(message, "name", None)

        if tool_name == expected_tool:
            return "PASS"

    return "FAIL"