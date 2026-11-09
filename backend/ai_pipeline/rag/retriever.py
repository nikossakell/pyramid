"""
ai_pipeline/rag/retriever.py — ανάκτηση κομματιών για μια ερώτηση (το μέρος του 5.2 που δεν θέλει LLM).

Χρησιμοποιείται από το scripts/eval_retrieval.py τώρα και από το rag_qa.py (Krikri) αργότερα.
Το ίδιο embedder αντικείμενο κάνει και τα passages και την ερώτηση· το ChromaIndex.load ελέγχει ότι το
μοντέλο της ερώτησης είναι αυτό με το οποίο χτίστηκε η βάση.
"""
from pathlib import Path

from .embedder import Embedder
from .index import ChromaIndex, Hit, _default_client

DEFAULT_K = 5   # όπως το final_plan (top 5)


class Retriever:
    def __init__(self, index: ChromaIndex, embedder: Embedder):
        if index.manifest["embedding_model"] != embedder.model_id:
            raise ValueError(f"index model {index.manifest['embedding_model']} != {embedder.model_id}")
        self.index, self.embedder = index, embedder

    @classmethod
    def from_dir(cls, rag_db: Path, embedder: Embedder, allow_draft: bool = False,
                 client_factory=_default_client) -> "Retriever":
        return cls(ChromaIndex.load(rag_db, expected_model=embedder.model_id, allow_draft=allow_draft,
                                    client_factory=client_factory), embedder)

    def search(self, question: str, k: int = DEFAULT_K, mode: str = "hybrid",
               exclude: frozenset[str] = frozenset()) -> list[Hit]:
        if not question.strip():
            return []
        return self.index.search(self.embedder.embed_query(question), question, k=k, mode=mode, exclude=exclude)
