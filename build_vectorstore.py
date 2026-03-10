import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

def build_vectorstore():
    print("📚 Loading knowledge base...")
    loader = TextLoader("faq.txt")
    docs = loader.load()
    
    # Split text into bite-sized chunks to feed to the LLM
    print("✂️ Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    splits = text_splitter.split_documents(docs)
    
    # Create embedings using the small, fast nomic model
    # Note: Requires `ollama pull nomic-embed-text`
    print("🧠 Generating Nomic embeddings and building FAISS index...")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    # Save the index locally to disk
    vectorstore.save_local("faiss_index")
    print("✅ Knowledge Base successfully vectorized and saved to 'faiss_index' directory.")
    
if __name__ == "__main__":
    build_vectorstore()
