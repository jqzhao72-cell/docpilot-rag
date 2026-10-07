import os


# 设置代理
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"


# 增加huggingface超时
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"


from sentence_transformers import CrossEncoder


print("开始下载Reranker模型...")


model = CrossEncoder(
    "BAAI/bge-reranker-base"
)


print("Reranker模型下载完成")