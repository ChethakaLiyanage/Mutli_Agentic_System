"""In-memory TF-IDF retrieval over durable controlled knowledge chunks."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from supabase import Client

from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import KnowledgeChunk, KnowledgeDocumentType
from backend.app.schemas.domain import EvidenceItem


DEFAULT_TOP_K = 5
DEFAULT_MINIMUM_SCORE = 0.08


class _KnowledgeRepository(Protocol):
    def list_knowledge_chunks(
        self,
        *,
        insurance_type: str = "motor",
        document_type: KnowledgeDocumentType | None = None,
    ) -> list[KnowledgeChunk]: ...


class KnowledgeRetriever:
    """Lazy lexical index; call ``refresh`` after successful ingestion."""

    def __init__(
        self,
        client: Client | None = None,
        *,
        repository: _KnowledgeRepository | None = None,
    ) -> None:
        if repository is None:
            if client is None:
                raise ValueError("client or repository is required")
            repository = RetrievalRepository(client)
        self.repository = repository
        self._lock = RLock()
        self._chunks: list[KnowledgeChunk] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._loaded = False

    def refresh(self) -> int:
        """Reload the durable corpus and deterministically rebuild the index."""
        chunks = self.repository.list_knowledge_chunks(insurance_type="motor")
        chunks = sorted(chunks, key=lambda item: item.chunk_id)
        vectorizer: TfidfVectorizer | None = None
        matrix = None
        if chunks:
            vectorizer = TfidfVectorizer(
                lowercase=False,
                tokenizer=str.split,
                preprocessor=None,
                token_pattern=None,
                ngram_range=(1, 2),
                sublinear_tf=True,
                norm="l2",
            )
            matrix = vectorizer.fit_transform(
                [item.normalized_content for item in chunks]
            )
        with self._lock:
            self._chunks = chunks
            self._vectorizer = vectorizer
            self._matrix = matrix
            self._loaded = True
        return len(chunks)

    def retrieve(
        self,
        query: str,
        insurance_type: str = "motor",
        top_k: int = DEFAULT_TOP_K,
        min_relevance_score: float = DEFAULT_MINIMUM_SCORE,
        *,
        intent: str | None = None,
        document_type: KnowledgeDocumentType | None = None,
    ) -> list[EvidenceItem]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not 0 <= min_relevance_score <= 1:
            raise ValueError("min_relevance_score must be between 0 and 1")
        normalized_query = preprocess_for_retrieval(query)
        if not normalized_query:
            return []
        if not self._loaded:
            self.refresh()
        with self._lock:
            chunks = list(self._chunks)
            vectorizer = self._vectorizer
            matrix = self._matrix
        if not chunks or vectorizer is None or matrix is None:
            return []
        query_vector = vectorizer.transform([normalized_query])
        scores = cosine_similarity(query_vector, matrix).ravel()
        ranked: list[tuple[float, KnowledgeChunk]] = []
        for score, chunk in zip(scores, chunks):
            if chunk.insurance_type != insurance_type:
                continue
            if document_type is not None and chunk.document_type != document_type:
                continue
            if float(score) >= min_relevance_score:
                ranked.append((float(score), chunk))
        ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
        evidence: list[EvidenceItem] = []
        for score, chunk in ranked[:top_k]:
            metadata = dict(chunk.metadata)
            metadata.update(
                {
                    "source_document_id": chunk.source_document_id,
                    "chunk_id": chunk.chunk_id,
                    "document_type": chunk.document_type,
                    "insurance_type": chunk.insurance_type,
                }
            )
            if intent is not None:
                metadata["query_intent"] = intent
            evidence.append(
                EvidenceItem(
                    evidence_id=chunk.chunk_id,
                    source_title=chunk.source_title,
                    section=chunk.section,
                    content=chunk.content,
                    score=score,
                    metadata=metadata,
                )
            )
        return evidence
