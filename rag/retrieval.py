from sentence_transformers import SentenceTransformer
import chromadb

from app.permissions import get_retrieval_where


class Retriever:
    """
    Chroma知识库查询模块
    """


    def __init__(self):

        # 加载Embedding模型
        self.model = SentenceTransformer(
            r"C:\Users\20111\.cache\huggingface\hub\models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2\snapshots\e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
        )


        # 连接Chroma数据库

        self.client = chromadb.PersistentClient(
            path="./chroma_db"
        )


        # 获取知识库

        self.collection = self.client.get_collection(
            name="company_docs"
        )



    def search(self, question, user_role, top_k=3):
        """
        输入问题
        返回:
        文档 + 来源信息
        """


        # ======================
        # 1. 问题Embedding
        # ======================

        question_embedding = self.model.encode(
            [question]
        )


        # ======================
        # 2. Chroma检索
        # ======================

        query_args = {
            "query_embeddings": [question_embedding[0].tolist()],
            "n_results": top_k,
        }

        where = get_retrieval_where(user_role)
        if where is not None:
            query_args["where"] = where

        results = self.collection.query(**query_args)


        # ======================
        # 3. 整理返回结果
        # ======================

        documents = results["documents"][0]

        metadatas = results["metadatas"][0]

        distances = results["distances"][0]



        retrieved_results = []


        for doc, metadata, distance in zip(
            documents,
            metadatas,
            distances
        ):

            retrieved_results.append(
                {
                    "content": doc,

                    "source": metadata["source"],

                    "chunk_id": metadata["chunk_id"],

                    "score": distance
                }
            )


        return retrieved_results
