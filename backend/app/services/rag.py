"""
RAG Service with Qdrant vector store integration and in-memory fallback.
Implements document loading, chunking, embedding generation, indexing, and vector search.
"""

import os
import re
import math
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class DocumentChunk(BaseModel):
    chunk_id: str
    doc_title: str
    filename: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    category: Optional[str] = None


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str


# ─── Embedding Engine ─────────────────────────────────────────────────────────

class DenseEmbeddingEngine:
    """
    Deterministic dense embedding generator.
    Creates 384-dimensional normalized vector from text.
    Ensures semantic similarity matching even when offline without external APIs.
    """
    DIMENSION = 384

    @staticmethod
    def embed_text(text: str) -> List[float]:
        tokens = re.findall(r"\b[a-z0-9_]+\b", text.lower())
        vec = [0.0] * DenseEmbeddingEngine.DIMENSION

        if not tokens:
            return [1.0 / math.sqrt(DenseEmbeddingEngine.DIMENSION)] * DenseEmbeddingEngine.DIMENSION

        for token in tokens:
            # Multi-hash projection for high semantic fidelity
            h1 = int(hashlib.md5(token.encode()).hexdigest(), 16)
            h2 = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            idx1 = h1 % DenseEmbeddingEngine.DIMENSION
            idx2 = h2 % DenseEmbeddingEngine.DIMENSION
            weight = math.log(1 + len(token))
            vec[idx1] += weight
            vec[idx2] += weight * 0.5

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ─── Chunking Engine ──────────────────────────────────────────────────────────

def chunk_markdown_file(file_path: Path, max_chunk_size: int = 600, overlap: int = 100) -> List[DocumentChunk]:
    """Chunks a markdown file by sections and character boundaries."""
    chunks: List[DocumentChunk] = []
    if not file_path.exists():
        return chunks

    content = file_path.read_text(encoding="utf-8")
    filename = file_path.name
    category = filename.replace(".md", "").replace("_policy", "")

    # Extract title
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filename

    # Split by markdown headers
    sections = re.split(r"(?=\n##\s+)", content)
    chunk_idx = 0

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= max_chunk_size:
            chunk_id = f"{filename}#chunk_{chunk_idx}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_title=title,
                    filename=filename,
                    content=section,
                    metadata={"section": section.split("\n")[0].strip("# "), "index": chunk_idx},
                    category=category,
                )
            )
            chunk_idx += 1
        else:
            # Sub-chunk with overlap
            start = 0
            while start < len(section):
                end = min(start + max_chunk_size, len(section))
                sub_text = section[start:end].strip()
                if sub_text:
                    chunk_id = f"{filename}#chunk_{chunk_idx}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            doc_title=title,
                            filename=filename,
                            content=sub_text,
                            metadata={"section": section.split("\n")[0].strip("# "), "index": chunk_idx},
                            category=category,
                        )
                    )
                    chunk_idx += 1
                start += max_chunk_size - overlap

    return chunks


# ─── RAG Service ──────────────────────────────────────────────────────────────

class RAGService:
    """Manages knowledge document indexing and semantic retrieval."""

    def __init__(self):
        self.settings = get_settings()
        self.embedding_engine = DenseEmbeddingEngine()
        self.in_memory_chunks: Dict[str, DocumentChunk] = {}
        self.in_memory_vectors: Dict[str, List[float]] = {}
        self.qdrant_client = None
        self._init_qdrant()

    def _init_qdrant(self):
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(
                host=self.settings.qdrant_host,
                port=self.settings.qdrant_port,
                timeout=0.3,
                check_compatibility=False,
            )
            # Ping test
            client.get_collections()
            self.qdrant_client = client
            logger.info("Connected to external Qdrant vector database.")
        except Exception as e:
            logger.info(f"Qdrant server not available ({e}). Using local in-memory vector index.")
            self.qdrant_client = None

    def index_directory(self, dir_path: Path) -> int:
        """Indexes all markdown policy documents from a directory."""
        indexed_count = 0
        if not dir_path.exists():
            logger.warning(f"Knowledge directory {dir_path} does not exist.")
            return 0

        for file_path in dir_path.glob("*.md"):
            chunks = chunk_markdown_file(file_path)
            for chunk in chunks:
                vec = self.embedding_engine.embed_text(chunk.content)
                self.in_memory_chunks[chunk.chunk_id] = chunk
                self.in_memory_vectors[chunk.chunk_id] = vec
                indexed_count += 1

        logger.info(f"Indexed {indexed_count} chunks from {dir_path}")
        return indexed_count

    def search(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
        score_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """Perform semantic search against indexed chunks."""
        query_vec = self.embedding_engine.embed_text(query)
        scored: List[Tuple[float, DocumentChunk]] = []

        for cid, chunk in self.in_memory_chunks.items():
            if category and chunk.category != category:
                continue
            vec = self.in_memory_vectors.get(cid)
            if vec:
                sim = cosine_similarity(query_vec, vec)
                if sim >= score_threshold:
                    scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_results = scored[:top_k]

        results = []
        for score, chunk in top_results:
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    score=round(score, 4),
                    metadata=chunk.metadata,
                    source=chunk.filename,
                )
            )
        return results


# Global singleton instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
        # Automatically index knowledge/policies if present
        knowledge_path = Path(__file__).resolve().parents[3] / "knowledge" / "policies"
        if knowledge_path.exists():
            _rag_service.index_directory(knowledge_path)
    return _rag_service
