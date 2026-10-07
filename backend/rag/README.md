# RAG Core

`rag/` 是 DocPilot 后端可复用的 RAG 核心。它不处理 HTTP、登录权限、Vue 状态或页面展示。

## 模块位置

| 能力 | 文件 |
| --- | --- |
| 本地 Embedding | `embedding.py` |
| Dense Retrieval | `retrieval.py` |
| BM25 Sparse Retrieval | `sparse_retrieval.py` |
| Dense + BM25 + RRF | `hybrid_retrieval.py` |
| BGE Reranker、二阶段融合、Reference penalty | `reranker.py` |
| Prompt 构造 | `prompt.py` |
| DeepSeek 客户端 | `llm.py` |
| 端到端问答编排 | `pipeline.py` |
| 文档解析与切分 | `ingestion/` |
| Chroma 写入封装 | `vector_store.py` |

## 对外复用入口

业务 API、命令行脚本或后续任务队列应优先调用高层入口：

```python
from rag.pipeline import PaperRAGPipeline

pipeline = PaperRAGPipeline()
result = pipeline.answer("your question")
```

需要单独评估召回时再使用 `Retriever`、`BM25Retriever`、`HybridRetriever` 或 `Reranker`。调用方不应复制 RRF、Reference 检测或最终排序代码。

## 依赖限制

- 可以依赖 `rag` 内部模块和第三方模型/存储库。
- 不应依赖 `app`、`scripts`、`evaluation`、`tests` 或 `frontend`。
- 数据路径以 `backend/` 为运行目录；路径约定见 `data/README.md`。
