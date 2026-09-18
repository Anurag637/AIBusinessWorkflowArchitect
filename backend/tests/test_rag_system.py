"""
Unit & integration tests for RAG system, document chunking, semantic search, and API.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.rag import (
    RAGService,
    DenseEmbeddingEngine,
    cosine_similarity,
    chunk_markdown_file,
)


@pytest.fixture
def sample_policy_file(tmp_path):
    f = tmp_path / "sample_policy.md"
    f.write_text(
        "# Laptop Equipment Policy\n\n"
        "## Section 1: Standard Limits\n"
        "IT department can provision laptops up to ₹25,000 directly without manager sign-off.\n\n"
        "## Section 2: Manager Approval\n"
        "Any hardware request exceeding ₹25,000 requires explicit director or manager approval.\n",
        encoding="utf-8"
    )
    return f


def test_chunk_markdown_file(sample_policy_file):
    chunks = chunk_markdown_file(sample_policy_file)
    assert len(chunks) == 3
    assert chunks[0].doc_title == "Laptop Equipment Policy"
    assert "25,000" in chunks[1].content or "25,000" in chunks[2].content


def test_embedding_and_similarity():
    engine = DenseEmbeddingEngine()
    v1 = engine.embed_text("laptop equipment request policy")
    v2 = engine.embed_text("computer hardware policy and limits")
    v3 = engine.embed_text("recipe for cooking chocolate cake")

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated


def test_rag_service_search(tmp_path, sample_policy_file):
    service = RAGService()
    count = service.index_directory(tmp_path)
    assert count == 3

    results = service.search("laptop approval under 25000", top_k=2)
    assert len(results) >= 1
    assert "sample_policy.md" in results[0].source
    assert results[0].score > 0.0


def test_knowledge_api_endpoints():
    client = TestClient(app)

    # Re-index
    idx_resp = client.post("/api/v1/knowledge/index")
    assert idx_resp.status_code == 200
    assert idx_resp.json()["status"] == "success"

    # Search
    search_resp = client.post(
        "/api/v1/knowledge/search",
        json={"query": "laptop equipment spending limits ₹25000", "top_k": 3},
    )
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert data["status"] == "success"
    assert data["total_results"] >= 1
    # Check that equipment_policy is in results
    sources = [r["source"] for r in data["results"]]
    assert any("equipment" in s.lower() for s in sources)
