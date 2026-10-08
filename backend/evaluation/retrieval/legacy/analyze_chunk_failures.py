import json
from pathlib import Path

from rag.retrieval import Retriever


EVAL_FILE = Path(__file__).resolve().parents[2] / "datasets" / "legacy" / "rag_eval.json"

USER_ROLE = "hr"

# 这里取10个，方便分析：
# 正确Chunk是不是其实排在Top6~Top10
RETRIEVER_TOP_K = 10


with open(EVAL_FILE, "r", encoding="utf-8") as f:
    eval_data = json.load(f)


retriever = Retriever()


def normalize_text(text):
    """
    统一处理空格、换行、制表符，
    避免因为PDF排版导致关键词匹配失败。
    """
    return (
        text.replace(" ", "")
            .replace("\n", "")
            .replace("\r", "")
            .replace("\t", "")
    )


def is_relevant_chunk(
    doc,
    expected_source,
    expected_keywords
):
    source = doc.get("source", "")

    # 对Chunk正文做标准化
    content = normalize_text(
        doc.get("content", "")
    )

    # 必须来自正确文档
    if source != expected_source:
        return False

    # 关键词也做相同标准化后再匹配
    return all(
        normalize_text(keyword) in content
        for keyword in expected_keywords
    )


failure_count = 0


for item in eval_data:

    question = item["question"]
    expected_source = item["expected_source"]
    expected_keywords = item["expected_keywords"]

    docs = retriever.search(
        question,
        USER_ROLE,
        top_k=RETRIEVER_TOP_K
    )


    # ==================================================
    # 判断Top5是否存在真正相关Chunk
    # ==================================================

    top5_hit = any(
        is_relevant_chunk(
            doc,
            expected_source,
            expected_keywords
        )
        for doc in docs[:5]
    )


    # Top5已经正确，不需要做失败分析
    if top5_hit:
        continue


    failure_count += 1


    print("\n" + "=" * 100)

    print(f"失败案例 #{failure_count}")
    print(f"问题ID: {item['id']}")
    print(f"问题: {question}")

    print(f"\n标准来源:")
    print(expected_source)

    print(f"\n标准关键词:")
    print(expected_keywords)


    # ==================================================
    # 检查正确文档有没有进入Top10
    # ==================================================

    correct_source_ranks = []

    for rank, doc in enumerate(docs, start=1):

        if doc.get("source") == expected_source:
            correct_source_ranks.append(rank)


    if correct_source_ranks:
        print(
            "\n正确文档在Top10中的位置:",
            correct_source_ranks
        )
    else:
        print(
            "\n正确文档在Top10中完全没有出现"
        )


    # ==================================================
    # 打印Top10 Chunk
    # ==================================================

    print("\n【Retriever Top10】")


    for rank, doc in enumerate(
        docs,
        start=1
    ):

        source = doc.get(
            "source",
            "未知来源"
        )

        chunk_id = doc.get(
            "chunk_id",
            "未知"
        )

        distance = doc.get(
            "score",
            0
        )

        content = doc.get(
            "content",
            ""
        )


        # 判断是不是正确文档
        source_match = (
            source == expected_source
        )


        # 检查每个关键词是否出现
        content = doc.get(
           "content",
            ""
)

        normalized_content = normalize_text(content)

        keyword_status = {
         keyword: normalize_text(keyword) in normalized_content
          for keyword in expected_keywords
}


        # 判断这个Chunk是否完全满足标准
        chunk_match = is_relevant_chunk(
            doc,
            expected_source,
            expected_keywords
        )


        print("\n" + "-" * 100)

        print(f"Top{rank}")

        print(f"source: {source}")
        print(f"chunk_id: {chunk_id}")
        print(f"distance: {distance:.4f}")

        print(
            f"是否正确文档: "
            f"{'是' if source_match else '否'}"
        )

        print(
            f"关键词匹配情况: "
            f"{keyword_status}"
        )

        print(
            f"是否为标准相关Chunk: "
            f"{'是' if chunk_match else '否'}"
        )

        print("\nChunk正文:")
        print(content)


print("\n" + "=" * 100)

print("Chunk失败案例分析完成")
print(f"失败问题数量: {failure_count}")
print(f"总问题数量: {len(eval_data)}")

print(
    f"Chunk Recall@5失败率: "
    f"{failure_count / len(eval_data):.2%}"
)
