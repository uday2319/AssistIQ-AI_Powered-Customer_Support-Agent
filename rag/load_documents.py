from pathlib import Path
from langchain_community.document_loaders import TextLoader

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"

def load_knowledge_base():
    """
    Load all .txt files from the knowledge base.
    Returns a list of LangChain Document objects.
    """
    documents = []

    for file_path in KNOWLEDGE_BASE_DIR.glob("*.txt"):
        loader = TextLoader(str(file_path),encoding="utf-8")
        documents.extend(loader.load())

    return documents


if __name__ == "__main__":
    
    documents = load_knowledge_base()

    print(f"Loaded {len(documents)} documents.")

    for document in documents:
        print("\n--- Document ---")
        print("Source:", document.metadata["source"])
        print("Content:")
        print(document.page_content)
