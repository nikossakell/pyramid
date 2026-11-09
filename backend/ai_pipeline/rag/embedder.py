"""
ai_pipeline/rag/embedder.py — μετατροπή κειμένου σε διανύσματα.

E5Embedder: intfloat/multilingual-e5-large (MIT, 1024 διαστάσεις, έως 512 tokens).
Η κάρτα του μοντέλου ορίζει προθέματα "query: " για ερωτήσεις και "passage: " για κείμενα, αλλιώς
«performance degradation». Τα διανύσματα κανονικοποιούνται, άρα εσωτερικό γινόμενο = συνημίτονο.

ΔΙΟΡΘΩΣΗ ΣΦΑΛΜΑΤΟΣ ΤΟΥ final_plan: εκεί το ingestion κάνει embedding με το e5 αλλά το query περνά
query_texts στο ChromaDB, που χρησιμοποιεί άλλο μοντέλο (all-MiniLM-L6-v2, 384 διαστάσεις). Εδώ ΚΑΙ τα
δύο περνούν από το ίδιο αντικείμενο, και το ευρετήριο αρνείται να φορτωθεί με άλλο μοντέλο.

HashingEmbedder: μόνο για tests. Λεξικό διάνυσμα χωρίς μοντέλο, ώστε τα tests να τρέχουν παντού.
"""
import hashlib
import re
from typing import Optional, Protocol

import numpy as np

E5_MODEL = "intfloat/multilingual-e5-large"
E5_MAX_TOKENS = 512


class Embedder(Protocol):
    model_id: str
    dim: int

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


class E5Embedder:
    def __init__(self, model_name: str = E5_MODEL, revision: Optional[str] = None,
                 device: Optional[str] = None, batch_size: int = 16, model=None):
        """model: για tests (αντικείμενο με .encode και .tokenizer). Αλλιώς φορτώνεται με sentence-transformers."""
        if model is None:
            from sentence_transformers import SentenceTransformer   # βαριά εξάρτηση: μόνο όταν χρειάζεται
            model = SentenceTransformer(model_name, revision=revision, device=device)
        self._model = model
        self.model_id = f"{model_name}@{revision or 'default'}"
        self.batch_size = batch_size
        self.dim = int(self._encode(["query: dim probe"]).shape[1])

    def _encode(self, texts: list[str]) -> np.ndarray:
        v = self._model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                               convert_to_numpy=True, show_progress_bar=len(texts) > 64)
        return np.asarray(v, dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([f"query: {text}"])[0]

    def count_truncated(self, texts: list[str]) -> list[int]:
        """Δείκτες κειμένων που ξεπερνούν τα 512 tokens μαζί με το πρόθεμα (θα κοπούν από το μοντέλο)."""
        tok = getattr(self._model, "tokenizer", None)
        if tok is None:
            return []
        return [i for i, t in enumerate(texts)
                if len(tok(f"passage: {t}", add_special_tokens=True)["input_ids"]) > E5_MAX_TOKENS]


class HashingEmbedder:
    """Bag-of-words με hashing. ΟΧΙ για παραγωγή: δεν καταλαβαίνει νόημα ούτε άλλη γλώσσα."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.model_id = f"hashing-bow-{dim}"

    def _vec(self, text: str) -> np.ndarray:
        from ai_pipeline.presentation.lexicon import normalize   # ίδια κανονικοποίηση με τον validator
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"\w+", normalize(text)):
            stem = tok[:6]   # χοντρή «ρίζα» ώστε σίδηρος / σιδήρου να ταιριάζουν
            v[int(hashlib.md5(stem.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)
