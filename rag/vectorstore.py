from pathlib import Path

from langchain_chroma import Chroma

from rag.split_documents import split_documents
from rag.embeddings import create_embedding_model

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "knowledge_base"


def create_vector_store(rebuild: bool = False, persist_directory: Path = CHROMA_DIR):
    """
    Load the Chroma vector database, building it only if it is empty.

    Before, Chroma.from_documents ran on every start and added all
    chunks again, so the database filled up with duplicates.

    Run `python -m rag.vectorstore` to rebuild it after editing
    the files in knowledge_base/.
    """

    embeddings = create_embedding_model()

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(persist_directory),
    )

    if rebuild:
        vector_store.reset_collection()

    if vector_store._collection.count() == 0:
        vector_store.add_documents(split_documents())

    return vector_store


if __name__ == "__main__":
    vector_store = create_vector_store(rebuild=True)

    print("Chroma vector database rebuilt successfully!")
    print("Location:", CHROMA_DIR)
    print("Chunks:", vector_store._collection.count())
