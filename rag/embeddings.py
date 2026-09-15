from langchain_huggingface import HuggingFaceEmbeddings

def create_embedding_model():
    """
    Create a HuggingFaceEmbeddings model for generating embeddings.
    Returns the embedding model.
    """
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return embeddings

if __name__=="__main__":
    embeddings=create_embedding_model()
    text = "Can I get a refund for a damaged product?"

    vector=embeddings.embed_query(text)
    print("vector length:",len(vector))
    print("first 10 values:",vector[:10])

