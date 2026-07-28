from sentence_transformers import SentenceTransformer
import chromadb


# =====================
# 1. 文档
# =====================

document = """
第一章 年假制度

正式员工每年享有10天带薪年假。
员工申请年假时，需要提前三个工作日提交申请。
年假申请需要经过部门负责人审批。

第二章 试用期制度

新员工的试用期为3个月。
试用期结束后，公司会根据员工表现进行转正考核。

第三章 报销制度

员工因工作产生的交通费用可以申请报销。
报销申请需要提供真实有效的发票。
"""


# =====================
# 2. 文本切分
# =====================

def split_text(text):

    paragraphs = text.strip().split("\n")

    chunks = []

    for p in paragraphs:

        p = p.strip()

        if p:
            chunks.append(p)

    return chunks



chunks = split_text(document)


print("文本块数量:", len(chunks))


# =====================
# 3. Embedding模型
# =====================

model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


embeddings = model.encode(chunks)


print(
    "Embedding维度:",
    embeddings.shape
)


# =====================
# 4. 创建Chroma数据库
# =====================


client = chromadb.PersistentClient(
    path="./chroma_db"
)


collection = client.get_or_create_collection(
    name="company_docs"
)



# =====================
# 5. 保存向量
# =====================


collection.add(
    ids=[
        str(i)
        for i in range(len(chunks))
    ],

    documents=chunks,

    embeddings=[
        embedding.tolist()
        for embedding in embeddings
    ]
)


print("向量保存完成")


# =====================
# 6. 查询
# =====================


question = "员工一年有多少天年假？"


question_embedding = model.encode(
    [question]
)



results = collection.query(
    query_embeddings=[
        question_embedding[0].tolist()
    ],

    n_results=3
)


print("\n查询结果:")


for doc in results["documents"][0]:

    print("----------------")

    print(doc)