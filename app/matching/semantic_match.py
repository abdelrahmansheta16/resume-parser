from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

_model = None


def get_embedding_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(config.embedding_model)
            logger.info("Loaded embedding model: %s", config.embedding_model)
        except ImportError:
            logger.warning("sentence-transformers not installed — semantic matching disabled")
            return None
        except Exception as e:
            logger.warning("Failed to load embedding model: %s", e)
            return None
    return _model


def compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using embeddings."""
    model = get_embedding_model()
    if model is None:
        return 0.0

    try:
        embeddings = model.encode([text_a, text_b], convert_to_tensor=True)
        from sentence_transformers.util import cos_sim
        similarity = cos_sim(embeddings[0], embeddings[1]).item()
        # Scale from [-1, 1] to [0, 100]
        return max(0.0, min(100.0, (similarity + 1) * 50))
    except Exception as e:
        logger.warning("Semantic similarity failed: %s", e)
        return 0.0
