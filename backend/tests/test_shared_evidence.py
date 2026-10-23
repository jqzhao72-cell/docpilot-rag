"""The fixed answer path and Agent tool share exact production evidence ordering."""
import unittest
from unittest.mock import patch

from rag.evidence import EvidenceRetriever
from rag.pipeline import PaperRAGPipeline
from rag.reranker import second_stage_rank_fusion
from app import knowledge


class Hybrid:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def search(self, query, top_k, metadata_filter=None):
        self.calls.append((query, top_k, metadata_filter))
        return [dict(x) for x in self.rows[:top_k]]


class Reranker:
    def rerank(self, query, candidates, top_k):
        return [{**x, 'rerank_score': 1.0} for x in reversed(candidates)][:top_k]


class LLM:
    def generate(self, prompt):
        return 'supported[1]'


class SharedEvidenceTests(unittest.TestCase):
    def test_same_second_rrf_and_reference_penalty_order(self):
        rows = [{'id': f'p{i}', 'text': 'et al. doi: References' if i == 0 else 'evidence',
                 'source': 'paper.pdf', 'section': 'References' if i == 0 else 'Methods',
                 'page_start': i + 1, 'page_end': i + 1, 'chunk_type': 'text'} for i in range(7)]
        h, ranker = Hybrid(rows), Reranker()
        expected = second_stage_rank_fusion(rows, ranker.rerank('question', rows, 20),
                    k=60, top_k=5, query='question', reference_rank_penalty=4)
        shared = EvidenceRetriever(h, ranker).retrieve_evidence('question')['retrieval_results']
        pipeline = PaperRAGPipeline(h, ranker, LLM()).answer('question')
        self.assertEqual([x['id'] for x in expected], [x['id'] for x in shared])
        self.assertEqual([x['id'] for x in shared], [x['id'] for x in pipeline['retrieval_results']])
        self.assertEqual(h.calls[0][1], 20)
        self.assertEqual(pipeline['answer'], 'supported[1]')

    def test_tool_has_no_llm_and_only_returns_authorized_real_rows(self):
        chunks = [{'id': 'real', 'text': 'authorized', 'source': 'paper.pdf',
                   'page_start': 7, 'page_end': 8, 'chunk_type': 'text', 'section': 'Methods'}]
        retriever = EvidenceRetriever(Hybrid(chunks), Reranker())
        with patch('app.knowledge.evidence_retriever', return_value=retriever), \
             patch('app.knowledge.generation_components') as llm:
            result = knowledge.search_evidence('q', 1, 'paper', chunks)
        llm.assert_not_called()
        self.assertTrue(result['has_evidence'])
        self.assertEqual(result['evidence'][0]['chunk_id'], 'real')
        self.assertEqual(result['evidence'][0]['page'], '7-8')
        self.assertEqual(result['evidence'][0]['text'], 'authorized')

    def test_no_accessible_content_never_loads_models(self):
        with patch('app.knowledge.evidence_retriever') as factory:
            self.assertEqual(knowledge.search_evidence('q', 5, 'paper', [])['evidence'], [])
        factory.assert_not_called()
