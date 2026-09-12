from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from tools.order_tools import get_order_status
from config import GOOGLE_API_KEY
from schemas import supportResponse
from prompts import support_prompt
from tools.customer_tools import get_customer

llm=ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY,
)
agent=create_agent(
    model=llm,
    tools=[get_order_status, get_customer]
)

customer_message=input("Customer: ")

result=agent.invoke({"messages":[{"role":"user", "content":customer_message}]})

print("\n--- Support Response ---")
final_message=result["messages"][-1]
answer=final_message.content[0]["text"]
print(answer)
