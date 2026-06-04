import sys
import os
# Reconfigure stdout to prevent encoding crashes on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from langchain_community.vectorstores import FAISS
from tools.rag.embedder import get_embedder
from config.settings import DATASET_NAME, FAISS_DB_PATH



def build_faiss_index():
    """Build FAISS index from dataset for disease-symptom retrieval."""
    from datasets import load_dataset
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

_cross_encoder_cache = None

def get_cross_encoder():
    """Lazily load and cache the CrossEncoder model for re-ranking."""
    global _cross_encoder_cache
    if _cross_encoder_cache is not None:
        return _cross_encoder_cache
        
    print("📥 Loading CrossEncoder (first time only)...")
    try:
        from sentence_transformers import CrossEncoder
        # Ms-Marco-MiniLM is lightweight (~80MB) and very accurate for passage ranking
        _cross_encoder_cache = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        print("✅ CrossEncoder loaded successfully")
    except Exception as e:
        print(f"⚠️ Error loading CrossEncoder: {e}. Falling back to standard FAISS retrieval.")
        _cross_encoder_cache = None
    return _cross_encoder_cache

def retrieve_semantic_results(query: str, k: int = 3):
    """Retrieve semantically similar medical entries from FAISS with Cross-Encoder re-ranking."""
    db = get_faiss_index()
    if not db:
        return []
        
    # Stage 1: Retrieve more candidate documents (e.g., 10 candidates)
    # This ensures we have a broader pool for the more precise Cross-Encoder to evaluate
    try:
        candidates = db.similarity_search(query, k=max(k * 3, 10))
    except Exception as e:
        print(f"⚠️ FAISS similarity search error: {e}")
        return []

    if not candidates:
        return []
        
    candidate_texts = [r.page_content for r in candidates]
    
    # Stage 2: Re-rank using Cross-Encoder
    encoder = get_cross_encoder()
    if encoder is not None:
        try:
            # Pair query with each candidate text
            pairs = [[query, text] for text in candidate_texts]
            scores = encoder.predict(pairs)
            
            # Sort by score descending
            scored_candidates = sorted(zip(scores, candidate_texts), key=lambda x: x[0], reverse=True)
            
            # Select top k
            top_results = [text for score, text in scored_candidates[:k]]
            print(f"🔍 [Re-ranker] Re-ranked {len(candidate_texts)} candidates. Top score: {scored_candidates[0][0]:.4f}")
            return top_results
        except Exception as e:
            print(f"⚠️ CrossEncoder scoring error: {e}. Falling back to default similarity order.")
            
    # Fallback to default FAISS order
    return candidate_texts[:k]


if __name__ == "__main__":
    build_faiss_index()

