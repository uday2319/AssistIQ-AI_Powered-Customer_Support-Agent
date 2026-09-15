from langchain.tools import tool
from rag.retriever import get_retriever

retriever=get_retriever()

@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the company knowledge base for information about
    refunds, shipping, cancellations, and company policies.
    """
    documents=retriever.invoke(query)

    if not documents:
        return "No relevant information found in the knowledge base."

    results=[]
    for doc in documents:
        results.append(doc.page_content)

    return "\n\n".join(results)
