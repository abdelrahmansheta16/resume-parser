from __future__ import annotations

import hashlib
import json

from app.api.schemas import ParsedResume, VectorSearchHit, VectorSearchResult
from app.core.logging import get_logger
from app.core.paths import CHROMADB_DIR
from app.models.config import get_config

logger = get_logger(__name__)

_collection = None


def _get_collection():
    """Get or create the ChromaDB collection (lazy singleton)."""
    global _collection
    if _collection is not None:
        return _collection

    import chromadb

    config = get_config()
    persist_dir = str(CHROMADB_DIR)
    client = chromadb.PersistentClient(path=persist_dir)

    _collection = client.get_or_create_collection(
        name=config.vector_collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection '%s' ready (%d docs)", config.vector_collection_name, _collection.count())
    return _collection


def _resume_to_text(resume: ParsedResume) -> str:
    """Build a searchable text representation of a resume."""
    parts = []
    if resume.candidate_name:
        parts.append(resume.candidate_name)
    if resume.summary:
        parts.append(resume.summary)
    if resume.skills:
        parts.append("Skills: " + ", ".join(resume.skills))
    for exp in resume.experience:
        if exp.job_title:
            parts.append(exp.job_title)
        if exp.company:
            parts.append(exp.company)
        if exp.description:
            parts.append(" ".join(exp.description))
    for edu in resume.education:
        if edu.degree:
            parts.append(edu.degree)
        if edu.institution:
            parts.append(edu.institution)
    return "\n".join(parts)


def _generate_id(resume: ParsedResume) -> str:
    """Generate a deterministic ID for a resume."""
    content = f"{resume.candidate_name}|{resume.email}|{','.join(resume.skills[:5])}"
    return hashlib.md5(content.encode()).hexdigest()


def index_resume(resume: ParsedResume) -> str:
    """Index a parsed resume into ChromaDB. Returns the document ID."""
    collection = _get_collection()
    doc_id = _generate_id(resume)
    doc_text = _resume_to_text(resume)

    metadata = {
        "candidate_name": resume.candidate_name or "",
        "skills": json.dumps(resume.skills),
        "total_years_experience": resume.total_years_experience,
        "location": resume.location or "",
    }

    collection.upsert(
        ids=[doc_id],
        documents=[doc_text],
        metadatas=[metadata],
    )
    logger.info("Indexed resume '%s' as %s", resume.candidate_name, doc_id)
    return doc_id


def search(query: str, n_results: int = 10) -> VectorSearchResult:
    """Search for resumes similar to query text."""
    collection = _get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()) if collection.count() > 0 else 1,
    )

    hits = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            similarity = max(0.0, 1.0 - distance)

            skills = []
            if "skills" in meta:
                try:
                    skills = json.loads(meta["skills"])
                except (json.JSONDecodeError, TypeError):
                    pass

            hits.append(VectorSearchHit(
                candidate_name=meta.get("candidate_name", ""),
                similarity_score=round(similarity, 4),
                skills=skills,
                resume_id=doc_id,
            ))

    return VectorSearchResult(
        query=query,
        hits=hits,
        total_indexed=collection.count(),
    )


def get_stats() -> dict:
    """Get collection statistics."""
    collection = _get_collection()
    return {
        "total_documents": collection.count(),
        "collection_name": collection.name,
    }


def clear() -> dict:
    """Clear all documents from the collection."""
    global _collection
    import chromadb

    config = get_config()
    persist_dir = str(CHROMADB_DIR)
    client = chromadb.PersistentClient(path=persist_dir)
    client.delete_collection(config.vector_collection_name)
    _collection = None
    logger.info("Cleared vector collection")
    return {"status": "cleared"}
