import os
import requests
import time
from langchain_core.embeddings import Embeddings
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key: str = None, model: str = "models/gemini-embedding-001"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please check your .env file.")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents using the Gemini batchEmbedContents API."""
        if not texts:
            return []
            
        embeddings = []
        chunk_size = 100
        for i in range(0, len(texts), chunk_size):
            # Sleep 15 seconds between batches to stay well below the free tier 15 RPM limit
            if i > 0:
                time.sleep(15)
                
            chunk = texts[i:i + chunk_size]
            url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:batchEmbedContents?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "requests": [
                    {
                        "model": self.model,
                        "content": {
                            "parts": [{"text": text}]
                        },
                        "task_type": "RETRIEVAL_DOCUMENT"
                    }
                    for text in chunk
                ]
            }
            
            # Retry with backoff
            max_retries = 4
            backoff = 20
            for attempt in range(max_retries):
                try:
                    response = requests.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    for emb in data.get("embeddings", []):
                        embeddings.append(emb["values"])
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Batch embedding failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        print(f"❌ Failed to embed batch after {max_retries} attempts: {e}")
                        raise e
                    
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query using the Gemini embedContent API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:embedContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "content": {
                "parts": [{"text": text}]
            },
            "task_type": "RETRIEVAL_QUERY"
        }
        
        max_retries = 4
        backoff = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["embedding"]["values"]
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Query embedding failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"❌ Failed to embed query after {max_retries} attempts: {e}")
                    raise e

def get_embedder():
    """Return the embedding model instance."""
    return GeminiEmbeddings()
