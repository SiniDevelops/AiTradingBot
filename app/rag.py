"""
RAG (Retrieval-Augmented Generation) module with vector store.
Uses FAISS for similarity search and local stub for embeddings.
"""
import json
import hashlib
import pickle
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

from app.db import insert_vector_chunk, get_vector_chunks_by_ticker, get_db
from app.models import RetrievedChunk


class EmbeddingProvider:
    """Interface for embedding providers."""
    
    def embed(self, text: str) -> List[float]:
        """Return embedding vector for text."""
        raise NotImplementedError


class LocalStubEmbedding(EmbeddingProvider):
    """Local stub that returns deterministic embeddings based on text hash."""
    
    EMBEDDING_DIM = 384
    
    def embed(self, text: str) -> List[float]:
        """Create deterministic embedding from text hash."""
        # Use first 4 bytes of SHA256 hash to seed random generation
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert to 32-bit integer and ensure it's within valid range
        seed = int.from_bytes(hash_bytes[:4], byteorder='big') & 0xFFFFFFFF
        
        rng = np.random.RandomState(seed)
        embedding = rng.randn(self.EMBEDDING_DIM).astype(np.float32)
        
        # Normalize to unit length
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding.tolist()


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embeddings (optional, requires API key)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found")
        # Would initialize OpenAI client here
    
    def embed(self, text: str) -> List[float]:
        """Get embedding from OpenAI API."""
        # Placeholder - would call OpenAI API
        raise NotImplementedError("Not yet implemented - use LocalStubEmbedding for MVP")


class VectorStore:
    """FAISS-based vector store with metadata lookup."""
    
    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or LocalStubEmbedding()
        self.embed_dim = self.embedding_provider.EMBEDDING_DIM
        self.index = faiss.IndexFlatL2(self.embed_dim) if HAS_FAISS else None
        self.metadata = []  # Parallel list with metadata
        self.ticker_indices = {}  # Map ticker to list of indices
    
    def add_chunk(self, ticker: str, layer: str, source_id: str, snippet: str, timestamp: Optional[datetime] = None):
        """Add a chunk to the vector store."""
        if not HAS_FAISS:
            # Fallback to DB-only storage
            insert_vector_chunk(ticker, layer, source_id, snippet, timestamp)
            return
        
        # Create embedding
        embedding = self.embedding_provider.embed(snippet)
        embedding_np = np.array([embedding], dtype=np.float32)
        
        # Add to FAISS index
        self.index.add(embedding_np)
        
        # Track metadata
        idx = len(self.metadata)
        self.metadata.append({
            "ticker": ticker,
            "layer": layer,
            "source_id": source_id,
            "snippet": snippet,
            "timestamp": timestamp
        })
        
        # Track ticker -> indices mapping
        if ticker not in self.ticker_indices:
            self.ticker_indices[ticker] = []
        self.ticker_indices[ticker].append(idx)
        
        # Also persist to DB
        insert_vector_chunk(ticker, layer, source_id, snippet, timestamp)
    
    def retrieve_for_ticker(self, ticker: str, query: str, top_k: int = 6) -> List[RetrievedChunk]:
        """Retrieve top-k similar chunks for a ticker."""
        if not HAS_FAISS:
            # Fallback to DB retrieval (semantic-like)
            return self._retrieve_from_db(ticker, top_k)
        
        if ticker not in self.ticker_indices or not self.ticker_indices[ticker]:
            return []
        
        # Create query embedding
        query_embedding = self.embedding_provider.embed(query)
        query_np = np.array([query_embedding], dtype=np.float32)
        
        # Search full index then filter by ticker
        distances, indices = self.index.search(query_np, min(top_k * 3, len(self.metadata)))
        
        results = []
        for idx in indices[0]:
            if idx < len(self.metadata):
                meta = self.metadata[idx]
                if meta["ticker"] == ticker:
                    results.append(RetrievedChunk(
                        layer=meta["layer"],
                        source_id=meta["source_id"],
                        snippet=meta["snippet"],
                        timestamp=meta["timestamp"],
                        metadata={"distance": float(distances[0][len(results)])}
                    ))
                    if len(results) >= top_k:
                        break
        
        return results
    
    def _retrieve_from_db(self, ticker: str, top_k: int) -> List[RetrievedChunk]:
        """Retrieve chunks from DB (fallback when FAISS unavailable)."""
        from app.db import get_vector_chunks_by_ticker
        
        chunks = get_vector_chunks_by_ticker(ticker)
        
        results = []
        for chunk in chunks[:top_k]:
            results.append(RetrievedChunk(
                layer=chunk["layer"],
                source_id=chunk["source_id"],
                snippet=chunk["snippet"],
                timestamp=chunk["timestamp"],
                metadata={"source": "db"}
            ))
        
        return results
    
    def save(self, path: str):
        """Save index to disk."""
        if HAS_FAISS and self.index:
            faiss.write_index(self.index, path)
            metadata_path = path.replace(".index", ".metadata")
            with open(metadata_path, "wb") as f:
                pickle.dump(self.metadata, f)
    
    def load(self, path: str):
        """Load index from disk."""
        if HAS_FAISS:
            self.index = faiss.read_index(path)
            metadata_path = path.replace(".index", ".metadata")
            if os.path.exists(metadata_path):
                with open(metadata_path, "rb") as f:
                    self.metadata = pickle.load(f)


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def init_vector_store():
    """Initialize vector store with existing chunks from DB."""
    vector_store = get_vector_store()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vector_chunks")
        for row in cursor.fetchall():
            meta = dict(row)
            if HAS_FAISS:
                vector_store.add_chunk(
                    ticker=meta["ticker"],
                    layer=meta["layer"],
                    source_id=meta["source_id"],
                    snippet=meta["snippet"],
                    timestamp=meta["timestamp"]
                )
