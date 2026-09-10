from langchain_google_genai import ChatGoogleGenerativeAI
from config import GOOGLE_API_KEY
from schemas import supportResponse
from prompts import support_prompt
llm=ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY,
)

structured_llm=llm.with_structured_output(supportResponse)

chain=support_prompt | structured_llm

customer_message=input("Customer: ")

response=chain.invoke({"customer_message": customer_message})

print("\n--- Support Response ---")
print("Answer:", response.answer)
print("Category:", response.category)
print("Requires Human:", response.requires_human)