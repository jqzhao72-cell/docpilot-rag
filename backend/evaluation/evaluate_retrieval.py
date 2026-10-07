import json
from pathlib import Path

from rag.retrieval import Retriever
from rag.reranker import Reranker


EVAL_FILE = Path("evaluation/rag_eval.json")

USER_ROLE = "hr"

# Retriever 先多召回一些，给 Reranker 足够候选
RETRIEVER_TOP_K = 10

# 最终统一评估前5
EVAL_TOP_K = 5


with open(EVAL_FILE, "r", encoding="utf-8") as f:
    eval_data = json.load(f)


retriever = Retriever()
reranker = Reranker()

#chunk中有没有正确答案
def evaluate_one_result(docs, expected_source):
    """
    对一组已经排好序的 docs 计算：
    Recall@1 / Recall@3 / Recall@5 / RR
    """

    retrieved_sources = [
        doc["source"]
        for doc in docs
    ]

    hit_at_1 = int(
        expected_source in retrieved_sources[:1]
    )

    hit_at_3 = int(
        expected_source in retrieved_sources[:3]
    )

    hit_at_5 = int(
        expected_source in retrieved_sources[:5]
    )

    reciprocal_rank = 0

    for rank, source in enumerate(
        retrieved_sources[:5],
        start=1
    ):
        if source == expected_source:
            reciprocal_rank = 1 / rank
            break

    return {
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "rr": reciprocal_rank
    }

def is_relevant_chunk(doc, expected_source, expected_keywords):
    content = doc.get("content", "")
    source = doc.get("source", "")

    # 先判断是不是正确文档
    if source != expected_source:
        return False

    # 再判断这个 Chunk 是否包含所有关键证据
    return all(
        keyword in content
        for keyword in expected_keywords
    )

#前多少个chunk有没有正确答案
def evaluate_chunk_recall(
    docs,
    expected_source,
    expected_keywords
):

    hit_at_1 = int(
        any(
            is_relevant_chunk(
                doc,
                expected_source,
                expected_keywords
            )
            for doc in docs[:1]
        )
    )

    hit_at_3 = int(
        any( 
            is_relevant_chunk(
                doc,
                expected_source,
                expected_keywords
            )
            for doc in docs[:3]
        )
    )

    hit_at_5 = int(
        any(
            is_relevant_chunk(
                doc,
                expected_source,
                expected_keywords
            )
            for doc in docs[:5]
        )
    )

    return {
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5
    }

# =========================
# Retriever统计
# =========================

retriever_hit_1 = 0
retriever_hit_3 = 0
retriever_hit_5 = 0
retriever_mrr_sum = 0


retriever_chunk_hit_1 = 0
retriever_chunk_hit_3 = 0
retriever_chunk_hit_5 = 0


# =========================
# Reranker统计
# =========================

reranker_hit_1 = 0
reranker_hit_3 = 0
reranker_hit_5 = 0
reranker_mrr_sum = 0

reranker_chunk_hit_1 = 0
reranker_chunk_hit_3 = 0
reranker_chunk_hit_5 = 0


total = len(eval_data)


for item in eval_data:

    question = item["question"]
    expected_source = item["expected_source"]
    expected_keywords = item["expected_keywords"]

    print("\n" + "=" * 100)
    print(f"问题ID: {item['id']}")
    print(f"问题: {question}")
    print(f"标准来源: {expected_source}")


    # =====================================================
    # 第一步：Retriever
    # =====================================================

    retrieved_docs = retriever.search(
        question,
        USER_ROLE,
        top_k=RETRIEVER_TOP_K
    )


    print("\n【Retriever 原始结果】")

    for rank, doc in enumerate(
        retrieved_docs[:EVAL_TOP_K],
        start=1
    ):
        print(
            f"Top{rank}: "
            f"{doc['source']} | "
            f"chunk={doc['chunk_id']} | "
            f"distance={doc['score']:.4f}"
        )


    retriever_result = evaluate_one_result(
        retrieved_docs,
        expected_source
    )


    retriever_hit_1 += retriever_result["hit_at_1"]
    retriever_hit_3 += retriever_result["hit_at_3"]
    retriever_hit_5 += retriever_result["hit_at_5"]
    retriever_mrr_sum += retriever_result["rr"]


    # =====================================================
    # 第二步：Reranker
    # =====================================================

    reranked_docs = reranker.rerank(
        question,
        retrieved_docs,
        top_k=EVAL_TOP_K
    )


    print("\n【Reranker 重排结果】")

    for rank, doc in enumerate(
        reranked_docs,
        start=1
    ):
        score = doc.get(
            "rerank_score",
            doc.get("score", 0)
        )

        print(
            f"Top{rank}: "
            f"{doc['source']} | "
            f"chunk={doc['chunk_id']} | "
            f"score={score:.4f}"
        )


    reranker_result = evaluate_one_result(
        reranked_docs,
        expected_source
    )

    retriever_chunk_result = evaluate_chunk_recall(
    retrieved_docs,
    expected_source,
    expected_keywords
    )


    retriever_chunk_hit_1 += (
    retriever_chunk_result["hit_at_1"]
     )

    retriever_chunk_hit_3 += (
    retriever_chunk_result["hit_at_3"]
     )

    retriever_chunk_hit_5 += (
    retriever_chunk_result["hit_at_5"]
     )



    reranker_hit_1 += reranker_result["hit_at_1"]
    reranker_hit_3 += reranker_result["hit_at_3"]
    reranker_hit_5 += reranker_result["hit_at_5"]
    reranker_mrr_sum += reranker_result["rr"]

    reranker_chunk_result = evaluate_chunk_recall(
    reranked_docs,
    expected_source,
    expected_keywords
     )


    reranker_chunk_hit_1 += (
    reranker_chunk_result["hit_at_1"]
     )

    reranker_chunk_hit_3 += (
    reranker_chunk_result["hit_at_3"]
     )

    reranker_chunk_hit_5 += (
    reranker_chunk_result["hit_at_5"]
     )


    print("\n【单题结果】")

    print(
        "Retriever:",
        f"R@1={retriever_result['hit_at_1']}",
        f"R@3={retriever_result['hit_at_3']}",
        f"R@5={retriever_result['hit_at_5']}",
        f"RR={retriever_result['rr']:.4f}"
    )
    print(
    "Retriever Chunk:",
    f"R@1={retriever_chunk_result['hit_at_1']}",
    f"R@3={retriever_chunk_result['hit_at_3']}",
    f"R@5={retriever_chunk_result['hit_at_5']}"
    )

    print(
        "Reranker:",
        f"R@1={reranker_result['hit_at_1']}",
        f"R@3={reranker_result['hit_at_3']}",
        f"R@5={reranker_result['hit_at_5']}",
        f"RR={reranker_result['rr']:.4f}"
    )

    print(
    "Reranker Chunk:",
    f"R@1={reranker_chunk_result['hit_at_1']}",
    f"R@3={reranker_chunk_result['hit_at_3']}",
    f"R@5={reranker_chunk_result['hit_at_5']}"
    )


# =====================================================
# 最终结果
# =====================================================

retriever_recall_1 = retriever_hit_1 / total
retriever_recall_3 = retriever_hit_3 / total
retriever_recall_5 = retriever_hit_5 / total
retriever_mrr = retriever_mrr_sum / total

retriever_chunk_recall_1 = (
    retriever_chunk_hit_1 / total
)

retriever_chunk_recall_3 = (
    retriever_chunk_hit_3 / total
)

retriever_chunk_recall_5 = (
    retriever_chunk_hit_5 / total
)


reranker_recall_1 = reranker_hit_1 / total
reranker_recall_3 = reranker_hit_3 / total
reranker_recall_5 = reranker_hit_5 / total
reranker_mrr = reranker_mrr_sum / total

reranker_chunk_recall_1 = (
    reranker_chunk_hit_1 / total
)

reranker_chunk_recall_3 = (
    reranker_chunk_hit_3 / total
)

reranker_chunk_recall_5 = (
    reranker_chunk_hit_5 / total
)


print("\n" + "=" * 100)
print("最终对比结果")
print("=" * 100)

print("\n【Retriever】")
print(f"Recall@1: {retriever_recall_1:.2%}")
print(f"Recall@3: {retriever_recall_3:.2%}")
print(f"Recall@5: {retriever_recall_5:.2%}")
print(f"MRR: {retriever_mrr:.4f}")

print("\n【Retriever Chunk级】")
print(
    f"Chunk Recall@1: "
    f"{retriever_chunk_recall_1:.2%}"
)
print(
    f"Chunk Recall@3: "
    f"{retriever_chunk_recall_3:.2%}"
)
print(
    f"Chunk Recall@5: "
    f"{retriever_chunk_recall_5:.2%}"
)


print("\n【Retriever + Reranker】")
print(f"Recall@1: {reranker_recall_1:.2%}")
print(f"Recall@3: {reranker_recall_3:.2%}")
print(f"Recall@5: {reranker_recall_5:.2%}")
print(f"MRR: {reranker_mrr:.4f}")


print("\n【Retriever + Reranker Chunk级】")
print(
    f"Chunk Recall@1: "
    f"{reranker_chunk_recall_1:.2%}"
)
print(
    f"Chunk Recall@3: "
    f"{reranker_chunk_recall_3:.2%}"
)
print(
    f"Chunk Recall@5: "
    f"{reranker_chunk_recall_5:.2%}"
)
 