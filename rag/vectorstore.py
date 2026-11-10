import hashlib
from pathlib import Path

from langchain_chroma import Chroma

from rag.load_documents import KNOWLEDGE_BASE_DIR
from rag.split_documents import split_documents
from rag.embeddings import create_embedding_model

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_PREFIX = "knowledge_base_"


def knowledge_base_fingerprint() -> str:
    """
    A short code that changes whenever any knowledge-base file changes.
    Line endings are ignored so Windows and Linux give the same code.
    """
    digest = hashlib.sha256()
    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.txt")):
        digest.update(path.name.encode())
        digest.update(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode())
    return digest.hexdigest()[:12]


def create_vector_store(rebuild: bool = False, persist_directory: Path = CHROMA_DIR):
    """
    Load the Chroma vector database, building it only when needed.

    The collection is named after the knowledge-base fingerprint, so
    after the documents change (for example after editing policy.yaml
    and running `python -m utils.policy`), a fresh index is built
    automatically and old ones are removed.
    """

    embeddings = create_embedding_model()
    collection_name = COLLECTION_PREFIX + knowledge_base_fingerprint()

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_directory),
    )

    if rebuild:
        vector_store.reset_collection()

    if vector_store._collection.count() == 0:
        vector_store.add_documents(split_documents())

        # Remove indexes built from older versions of the documents.
        client = vector_store._client
        for collection in client.list_collections():
            name = getattr(collection, "name", collection)
            if name != collection_name and (
                name.startswith(COLLECTION_PREFIX) or name in ("knowledge_base", "langchain")
            ):
                client.delete_collection(name)

    return vector_store


if __name__ == "__main__":
    vector_store = create_vector_store(rebuild=True)

    print("Chroma vector database rebuilt successfully!")
    print("Location:", CHROMA_DIR)
    print("Chunks:", vector_store._collection.count())
