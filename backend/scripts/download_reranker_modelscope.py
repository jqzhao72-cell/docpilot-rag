from modelscope import snapshot_download


model_dir = snapshot_download(
    model_id="BAAI/bge-reranker-base",
    cache_dir="./models"
)


print("====================")
print("模型下载完成")
print(model_dir)