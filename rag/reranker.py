from sentence_transformers import CrossEncoder


class Reranker:


    def __init__(self):

      from sentence_transformers import CrossEncoder
import os


class Reranker:


    def __init__(self):

        model_path = os.path.abspath(
            "./models/models/BAAI--bge-reranker-base/snapshots/master"
        )


        self.model = CrossEncoder(
            model_path
        )


def rerank(
    self,
    query,
    docs,
    top_k=3
):

    # 如果Retriever没有召回任何文档
    # 直接返回空列表
    # 不再调用CrossEncoder
    if not docs:
        return []

    # 后面保留你原来的代码

        pairs = []


        for doc in documents:

            pairs.append(
                [
                    question,
                    doc["content"]
                ]
            )


        scores = self.model.predict(
            pairs
        )


        for doc, score in zip(
            documents,
            scores
        ):

            doc["rerank_score"] = float(score)



        documents.sort(
            key=lambda x:x["rerank_score"],
            reverse=True
        )


        return documents[:top_k]

    def rerank(
        self,
        question,
        documents,
        top_k=3
    ):

        pairs = []


        for doc in documents:

            pairs.append(
                [
                    question,
                    doc["content"]
                ]
            )


        scores = self.model.predict(
            pairs
        )


        for doc, score in zip(
            documents,
            scores
        ):

            doc["rerank_score"] = float(score)


        documents.sort(
            key=lambda x:x["rerank_score"],
            reverse=True
        )


        return documents[:top_k]