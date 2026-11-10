from pathlib import Path

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
        # Include the file name so the agent can say where the answer came from.
        source = Path(doc.metadata.get("source", "unknown")).name
        results.append(f"[Source: {source}]\n{doc.page_content}")

    return "\n\n".join(results)
