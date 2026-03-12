"""Tests for vector database module.

These tests require chromadb to be installed. They are skipped if chromadb is unavailable.
"""
import pytest

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from app.api.schemas import ParsedResume


@pytest.mark.skipif(not HAS_CHROMADB, reason="chromadb not installed")
class TestVectorDBStore:
    def setup_method(self):
        """Clear the collection before each test."""
        from app.vectordb import store
        store._collection = None

    def test_index_resume(self):
        from app.vectordb.store import index_resume
        resume = ParsedResume(
            candidate_name="Test User",
            email="test@example.com",
            skills=["Python", "Docker"],
            summary="Experienced backend developer",
        )
        doc_id = index_resume(resume)
        assert isinstance(doc_id, str)
        assert len(doc_id) > 0

    def test_search(self):
        from app.vectordb.store import index_resume, search
        resume = ParsedResume(
            candidate_name="Backend Dev",
            skills=["Python", "FastAPI", "Docker"],
            summary="Senior backend developer with Python expertise",
        )
        index_resume(resume)

        result = search("Python backend developer", n_results=5)
        assert result.total_indexed >= 1
        assert len(result.hits) >= 1

    def test_get_stats(self):
        from app.vectordb.store import get_stats
        stats = get_stats()
        assert "total_documents" in stats
        assert "collection_name" in stats

    def test_search_empty_collection(self):
        from app.vectordb.store import clear, search
        try:
            clear()
        except Exception:
            pass
        # Reset for fresh collection
        from app.vectordb import store
        store._collection = None
        result = search("test query", n_results=5)
        assert isinstance(result.hits, list)
