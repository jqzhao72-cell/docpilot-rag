"""Shared evidence-only pipeline; no answer generation or Agent dependency."""
from time import perf_counter

from rag.hybrid_retrieval import HybridRetriever
from rag.reranker import Reranker, second_stage_rank_fusion

DEFAULT_CANDIDATE_TOP_K = 20
DEFAULT_FINAL_TOP_K = 5
DEFAULT_REFERENCE_RANK_PENALTY = 4


class EvidenceRetriever:
    def __init__(self, hybrid_retriever=None, reranker=None,
                 candidate_top_k=DEFAULT_CANDIDATE_TOP_K, final_top_k=DEFAULT_FINAL_TOP_K,
                 reference_rank_penalty=DEFAULT_REFERENCE_RANK_PENALTY):
        for name, value in (('candidate_top_k', candidate_top_k), ('final_top_k', final_top_k)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f'{name} must be a positive integer')
        if isinstance(reference_rank_penalty, bool) or not isinstance(reference_rank_penalty, int) or reference_rank_penalty < 0:
            raise ValueError('reference_rank_penalty must be a non-negative integer')
        self.hybrid_retriever = hybrid_retriever or HybridRetriever()
        self.reranker = reranker or Reranker()
        self.candidate_top_k = candidate_top_k
        self.final_top_k = final_top_k
        self.reference_rank_penalty = reference_rank_penalty

    def retrieve_evidence(self, query, metadata_filter=None):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('query must be a non-empty string')
        query = query.strip()
        started = perf_counter()
        candidates = self.hybrid_retriever.search(query, top_k=self.candidate_top_k, metadata_filter=metadata_filter)
        retrieval_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        reranked = self.reranker.rerank(query, candidates, top_k=self.candidate_top_k)
        reranker_ms = (perf_counter() - started) * 1000
        results = second_stage_rank_fusion(candidates, reranked, k=60, top_k=self.final_top_k,
                    query=query, reference_rank_penalty=self.reference_rank_penalty)
        return {'retrieval_results': results,
                'timings': {'retrieval_ms': retrieval_ms, 'reranker_ms': reranker_ms}}
