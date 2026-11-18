import logging
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._init_model()
        return cls._instance

    def _init_model(self):
        try:
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
            # paraphrase-multilingual-MiniLM-L12-v2 supports Russian, English and 50+ languages
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._model = None

    def encode(self, text: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        Encode single text or list of texts into normalized embedding vectors.
        Returns numpy array of shape (dim,) or (batch_size, dim).
        """
        if self._model is None:
            self._init_model()
            if self._model is None:
                # Fallback dummy embedding if offline/error
                dim = settings.EMBEDDING_DIM
                if isinstance(text, str):
                    return np.zeros(dim, dtype=np.float32)
                return np.zeros((len(text), dim), dtype=np.float32)
        
        embeddings = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )
        return embeddings

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two normalized vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

embedding_service = EmbeddingService()
