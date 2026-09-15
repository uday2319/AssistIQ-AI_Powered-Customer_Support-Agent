from pathlib import Path

from langchain_chroma import Chroma

from rag.split_documents import split_documents
from rag.embeddings import create_embedding_model
 
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


def create_vector_store():
    """
    Create a Chroma vector database from our knowledge-base chunks.
    """


    chunks = split_documents()

    embeddings = create_embedding_model()


    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR)
    )

    return vector_store


if __name__ == "__main__":
    vector_store = create_vector_store()

    print("Chroma vector database created successfully!")
    print("Location:", CHROMA_DIR)