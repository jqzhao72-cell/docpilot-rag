from sentence_transformers import SentenceTransformer
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
def split_text(text: str) -> list[str]:
    paragraphs = text.strip().split("\n")

    chunks = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if paragraph:
            chunks.append(paragraph)

    return chunks


chunks = split_text(document)

for index, chunk in enumerate(chunks):
    print(f"Chunk {index}: {chunk}")

model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

chunk_embeddings = model.encode(chunks)

print("文本块数量：", len(chunks))
print("向量矩阵形状：", chunk_embeddings.shape)
print("第一个文本块的向量：")
print(chunk_embeddings[0])