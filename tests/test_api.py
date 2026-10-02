from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from api.main import app


client = TestClient(app)


def test_root():
    """Test the API health-check endpoint."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["messages"] == (
        "API is running successfully!"
    )


@patch("api.main.support_graph.invoke")
def test_chat_success(mock_invoke):
    """
    Test a successful /chat request.

    We mock LangGraph so this test does NOT call Gemini.
    """

    mock_invoke.return_value = {
        "messages": [
            AIMessage(content="Your order is currently processing.")
        ]
    }

    response = client.post(
        "/chat",
        json={
            "customer_id": "C002",
            "conversation_id": "conversation-001",
            "message": "Where is my order 10490?"
        },
    )

    assert response.status_code == 200

     
    assert response.json()["response"] == (
        "Your order is currently processing."
    )

    mock_invoke.assert_called_once()