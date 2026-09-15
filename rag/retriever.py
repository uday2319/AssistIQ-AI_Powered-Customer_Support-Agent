from rag.vectorstore import create_vector_store


def get_retriever():
    """
    Create a retriever that searches our Chroma vector database.
    """

    # Create/load the Chroma vector store.
    vector_store = create_vector_store()

    # Convert the vector store into a retriever.
    # k=2 means return the 2 most relevant chunks.
    retriever = vector_store.as_retriever(
        search_kwargs={"k": 3}
    )

    return retriever


if __name__ == "__main__":
    # Create the retriever.
    retriever = get_retriever()

    # This is the customer's question.
    question = "Can I get a refund for a damaged product?"

    # Search the vector database using semantic similarity.
    results = retriever.invoke(question)

    print(f"Found {len(results)} relevant chunks.")

    # Display the retrieved chunks.
    for i, document in enumerate(results):
        print(f"\n--- Result {i + 1} ---")
        print(document.page_content)
        print("Source:", document.metadata.get("source"))