from rag.load_documents import load_knowledge_base
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_documents():
    documents=load_knowledge_base()
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=100,
        chunk_overlap=20
    )

    chunks = splitter.split_documents(documents)
    return chunks

if __name__ == "__main__":
    chunks = split_documents()

    print(f"Created {len(chunks)} chunks.")

    # Display each chunk so we can inspect the result.
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i + 1} ---")
        print(chunk.page_content)
        print("Metadata:", chunk.metadata)