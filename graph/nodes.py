from langchain_google_genai import ChatGoogleGenerativeAI

from config import GOOGLE_API_KEY
from graph.state import SupportState
from tools.order_tools import get_order_status
from tools.customer_tools import get_customer
from tools.knowledge_tools import search_knowledge_base


llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY
)

llm_with_tools=llm.bind_tools([get_order_status, 
                                get_customer, 
                                search_knowledge_base])


def agent_node(state: SupportState):
    """
    Run the LLM using the current conversation state.
    """

    messages = state["messages"]

    response = llm_with_tools.invoke(messages)
 
    return {
        "messages": [response]
    }