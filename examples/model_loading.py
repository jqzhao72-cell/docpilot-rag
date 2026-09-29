from sentence_transformers import CrossEncoder
import os


model_path = os.path.abspath(
    "./models/models/BAAI--bge-reranker-base/snapshots/master"
)


print("模型路径:")
print(model_path)


model = CrossEncoder(
    model_path
)


print("Reranker模型加载成功")