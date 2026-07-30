from sentence_transformers import SentenceTransformer
import chromadb


class Retriever:
    """
    Chroma知识库查询模块
    """

    def __init__(self):

        # 加载Embedding模型
        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )


        # 连接已经保存的Chroma数据库
        self.client = chromadb.PersistentClient(
            path="./chroma_db"
        )


        # 获取之前创建的集合
        self.collection = self.client.get_collection(
            name="company_docs"
        )


    def search(self, question, top_k=3):
        """
        输入问题
        返回最相关文档
        """


        # 1. 问题向量化

        question_embedding = self.model.encode(
            [question]
        )


        # 2. Chroma查询

        results = self.collection.query(
            query_embeddings=[
                question_embedding[0].tolist()
            ],

            n_results=top_k
        )


        return results