import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datasets import load_dataset
from langchain_community.vectorstores import FAISS
from tools.rag.embedder import get_embedder
from config.settings import DATASET_NAME, FAISS_DB_PATH



def build_faiss_index():
    """Build FAISS index from dataset for disease-symptom retrieval."""
    print("📥 Loading dataset...")
    ds = load_dataset(DATASET_NAME, split="train")

    docs = []
    for row in ds:
        disease = row.get("Disease", "")
        symptoms = row.get("Symptoms", "")
        treatments = row.get("Treatments", "")

        text = (
            f"Disease: {disease}\n"
            f"Symptoms: {symptoms}\n"
            f"Treatments: {treatments}"
        )
        docs.append(text)

    print(f"✅ Loaded {len(docs)} records")
    embeddings = get_embedder()

    print("🔧 Building FAISS index...")
    db = FAISS.from_texts(docs, embedding=embeddings)
    db.save_local(FAISS_DB_PATH)
    print(f"✅ Index saved at: {FAISS_DB_PATH}")


# Global cache for FAISS index
_faiss_cache = None

def get_faiss_index():
    """Get or load FAISS index with caching to prevent disk I/O on every request."""
    global _faiss_cache
    if _faiss_cache is not None:
        return _faiss_cache
        
    print("📥 Loading FAISS index from disk (first time only)...")
    embeddings = get_embedder()
    if os.path.exists(FAISS_DB_PATH):
        try:
            _faiss_cache = FAISS.load_local(FAISS_DB_PATH, embeddings, allow_dangerous_deserialization=True)
            print("✅ FAISS index loaded into memory")
        except Exception as e:
            print(f"❌ Error loading FAISS index: {e}")
            return None
    else:
        print("⚠️ FAISS index not found. Please build it first.")
        return None
        
    return _faiss_cache

def retrieve_semantic_results(query: str, k: int = 3):
    """Retrieve semantically similar medical entries from FAISS."""
    db = get_faiss_index()
    if not db:
        return []
        
    results = db.similarity_search(query, k=k)
    return [r.page_content for r in results]


if __name__ == "__main__":
    build_faiss_index()

