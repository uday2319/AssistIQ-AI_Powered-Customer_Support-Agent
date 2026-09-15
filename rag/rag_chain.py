from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from config import GOOGLE_API_KEY
from rag.retriever import get_retriever


# Create the Gemini model.
# Gemini will generate the final answer using the retrieved context.
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY
)


# Create the retriever that searches our knowledge base.
retriever = get_retriever()


# Prompt that tells Gemini how to use the retrieved information.
prompt = ChatPromptTemplate.from_template(
    """
    You are a customer support assistant.

    Answer the customer's question using ONLY the provided
    knowledge-base context.

    If the answer cannot be found in the context, say:
    "I don't have enough information to answer that."

    Knowledge-base context:
    {context}

    Customer question:
    {question}
    """
)


def answer_question(question: str) -> str:
    """
    Retrieve relevant information and use Gemini
    to generate the final customer-support answer.
    """

    # Search the vector database for relevant documents.
    documents = retriever.invoke(question)

    # Extract the actual text from each retrieved Document.
    context = "\n\n".join(
        document.page_content
        for document in documents
    )

    # Put the retrieved context + customer question into our prompt.
    messages = prompt.invoke({
        "context": context,
        "question": question
    })

    # Ask Gemini to generate the final answer.
    response = llm.invoke(messages)

    return response.content
