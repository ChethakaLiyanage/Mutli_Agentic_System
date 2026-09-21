"""Verification script to evaluate Agent 2 TF-IDF retrieval against the expanded synthetic corpus in Supabase."""

from __future__ import annotations

import json
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.services.supabase_service import get_supabase_client


CORE_QUERIES = [
    "vehicle collision required documents",
    "windscreen damage documents",
    "theft claim documents",
    "flood claim documents",
    "police report requirement",
    "claim reporting timeline",
    "deductible/excess meaning",
    "claim status process",
]

NOISY_AND_CONVERSATIONAL_QUERIES = [
    "what documents do i need after a crash",
    "papers needed for accident claim",
    "my windscreen broke what do i submit",
    "car was stolen what documents are needed",
    "flood damaged my car what should i provide",
    "do i need a police report",
    "do i need my driving licence",
    "how long do i have to report an accident",
    "what happens after i submit my claim",
    "what is policy excess",
    "why was more information requested",
    "what docs needed if i crash car",
    "my glass broke what paper i need",
    "someone stole my car wat documents",
    "flood dmg claim what should i upload",
]


def test_query(retriever: KnowledgeRetriever, query: str, top_k: int = 3) -> dict:
    evidence = retriever.retrieve(query, top_k=top_k, min_relevance_score=0.05)
    results = []
    for item in evidence:
        results.append({
            "source_title": item.source_title,
            "section": item.section,
            "score": round(item.score, 4),
            "snippet": item.content[:160].replace("\n", " ") + "...",
            "synthetic": item.metadata.get("synthetic", False),
        })
    return {
        "query": query,
        "results_count": len(results),
        "top_results": results,
    }


def main():
    client = get_supabase_client()
    repo = RetrievalRepository(client)
    retriever = KnowledgeRetriever(repository=repo)
    total_chunks = retriever.refresh()
    print(f"=== KnowledgeRetriever Initialized: {total_chunks} Chunks Loaded ===\n")

    print("==================================================")
    print("1. CORE DOMAIN RETRIEVAL TESTS")
    print("==================================================")
    core_evals = []
    for query in CORE_QUERIES:
        res = test_query(retriever, query)
        core_evals.append(res)
        print(f"\nQuery: '{query}'")
        if not res["top_results"]:
            print("  [NO RESULTS FOUND]")
        for i, hit in enumerate(res["top_results"], 1):
            print(f"  {i}. [{hit['score']}] {hit['source_title']} -> {hit['section']}")
            print(f"     Snippet: {hit['snippet']}")

    print("\n==================================================")
    print("2. CONVERSATIONAL & NOISY QUERY TESTS")
    print("==================================================")
    noisy_evals = []
    for query in NOISY_AND_CONVERSATIONAL_QUERIES:
        res = test_query(retriever, query)
        noisy_evals.append(res)
        print(f"\nQuery: '{query}'")
        if not res["top_results"]:
            print("  [NO RESULTS FOUND]")
        for i, hit in enumerate(res["top_results"], 1):
            print(f"  {i}. [{hit['score']}] {hit['source_title']} -> {hit['section']}")
            print(f"     Snippet: {hit['snippet']}")

    # Save summary report
    report_file = "backend/data/retrieval_verification_results.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_indexed_chunks": total_chunks,
            "core_queries": core_evals,
            "noisy_queries": noisy_evals,
        }, f, indent=2)
    print(f"\nFull verification results written to {report_file}")


if __name__ == "__main__":
    main()
