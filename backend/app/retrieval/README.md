# Agent 2 classical retrieval

Controlled `.txt`, `.pdf`, and `.docx` files are extracted without OCR, split
by detected heading/page and then into overlapping 180-word chunks. Raw chunk
content is retained for evidence; deterministic normalized text is stored for
retrieval.

`knowledge_chunks` is the durable corpus. `KnowledgeRetriever` lazily loads all
motor chunks on its first query and builds an in-memory unigram/bigram TF-IDF
index. Ranking uses cosine similarity, defaults to five results and rejects
scores below `0.08`. Call `refresh()` after ingestion when a long-running
process must see newly stored chunks. Scikit-learn objects are never persisted.

Source IDs are stable for a document title and type. A content hash prevents
unchanged re-ingestion; changed documents upsert their stable chunks and remove
only stale chunks belonging to that same source.
