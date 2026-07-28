from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# ==========================
# 1. 原始文档
# ==========================

document = """
第一章 年假制度

正式员工每年享有10天带薪年假。
员工申请年假时，需要提前三个工作日提交申请。
年假申请需要经过部门负责人审批。

第二章 试用期制度

新员工的试用期为3个月。
试用期结束后，公司会根据员工表现进行转正考核。
试用期员工享有正常工资，但暂不享有年度奖金。

第三章 报销制度

员工因工作产生的交通费用可以申请报销。
报销申请需要提供真实有效的发票。
单笔超过1000元的费用，需要部门负责人额外审批。
"""


# ==========================
# 2. 文本切分
# ==========================

def split_text(text: str) -> list[str]:

    paragraphs = text.strip().split("\n")

    chunks = []

    for paragraph in paragraphs:

        paragraph = paragraph.strip()

        if paragraph:
            chunks.append(paragraph)

    return chunks



chunks = split_text(document)



print("====================")
print("文本切分结果")
print("====================")


for index, chunk in enumerate(chunks):

    print(
        f"Chunk {index}: {chunk}"
    )



# ==========================
# 3. 加载Embedding模型
# ==========================


model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)



# ==========================
# 4. 文档Embedding
# ==========================


chunk_embeddings = model.encode(
    chunks
)


print("\n====================")
print("Embedding结果")
print("====================")


print(
    "文本块数量:",
    len(chunks)
)


print(
    "向量维度:",
    chunk_embeddings.shape
)



# ==========================
# 5. 用户问题
# ==========================


question = "申请年假时这个怎么做？"



# ==========================
# 6. 问题Embedding
# ==========================


question_embedding = model.encode(
    [question]
)



# ==========================
# 7. 计算相似度
# ==========================


similarity_scores = cosine_similarity(
    question_embedding,
    chunk_embeddings
)[0]



# ==========================
# 8. 输出所有文本相似度
# ==========================


print("\n====================")
print("相似度结果")
print("====================")


for index, score in enumerate(similarity_scores):

    print(
        f"Chunk {index}: {score:.4f}"
    )



# ==========================
# 9. Top-K检索
# ==========================


top_k = 3


top_indices = np.argsort(
    similarity_scores
)[::-1][:top_k]



print("\n====================")
print(f"Top-{top_k}检索结果")
print("====================")


for rank, index in enumerate(top_indices):

    print(
        f"""
排名:
{rank + 1}

相似度:
{similarity_scores[index]:.4f}

文本:
{chunks[index]}
"""
    )