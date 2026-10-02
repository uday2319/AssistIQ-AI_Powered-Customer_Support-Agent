from pydantic import BaseModel,Field
from fastapi import FastAPI,HTTPException
from graph.graph import support_graph

app=FastAPI(title="AI Customer Support Agent",
            description="API for the Customer Support Agent",
            version="1.0.0")

class chatRequest(BaseModel):
    """
    Defines the JSON data that the client must send.

    Example:
    {
        "customer_id": "C002",
        "message": "Where is my order 10490?"
    }
    """
    customer_id: str = Field(
        min_length=1,
        description="Authenticated customer ID."
    )

    conversation_id: str = Field(
        min_length=1,
        description="Unique conversation/thread ID."
    )

    message: str = Field(
        min_length=1,
        description="Customer's message."
    )


class ChatResponse(BaseModel):
    """
    Standard response returned by our API.
    """
    customer_id: str
    response: str

@app.get("/")
def root():
    """
    Health-check endpoint.

    Returns a simple JSON object so we can verify
    that the API server is running.
    """
    return {
        "messages": "API is running successfully!"
    }

@app.post("/chat")
def chat(request:chatRequest):
    """
    Send a customer message to the LangGraph agent.

    FastAPI receives the request,
    converts it into our SupportState,
    and starts the existing graph.
    """
    config={
        "configurable":{
            "thread_id":request.conversation_id
        }    }
    try:
        result = support_graph.invoke(
                {
                    "customer_id": request.customer_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": request.message,
                        }
                    ],
                },
                config=config,
            )
        
        final_message=result["messages"][-1]
        if isinstance(final_message.content, list):

            response_text = ""

            for block in final_message.content:

                if isinstance(block, dict) and "text" in block:
                    response_text += block["text"]

        else:
            response_text = str(final_message.content)

        return ChatResponse(
            customer_id=request.customer_id,
            response=response_text,
            conversation_id=request.conversation_id,
        )

    except Exception as e:
        error_message = str(e)

        if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
            raise HTTPException(
                status_code=429,
                detail="AI service rate limit exceeded. Please try again later."
            )

        raise HTTPException(
            status_code=500,
            detail="Internal server error."
        )
     