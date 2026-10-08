# Backend Scripts

`scripts/` 只保存建库、模型准备、数据库初始化和运维诊断入口。检索、重排和完整 RAG 评估已迁入 [evaluation/](../evaluation/README.md)。可复用业务逻辑应放在 `rag/` 或 `app/`，而不是脚本中。

## 分类

- `init_db.py`、`set_admin.py`：数据库和管理员初始化。
- `ingest.py`、`rebuild_clean_*.py`：文档解析与索引构建。
- `download_reranker*.py`：本地模型准备。
- `diagnostics/`：SQLite、Chroma、用户和历史只读检查。
- 需要真实模型的检索/重排/RAG 检查：见 `evaluation/retrieval/`、`evaluation/benchmarks/`、`evaluation/rag/`；单元测试继续在 `tests/`。

## 运行方式

所有命令从 `backend/` 执行：

```powershell
..\.venv\Scripts\python.exe -m scripts.init_db
..\.venv\Scripts\python.exe -m scripts.diagnostics.check_chroma
```

脚本可以解析参数、打印进度和选择输入文件，但不得重新实现 Dense、BM25、RRF、Reranker、Prompt 或 LLM 调用链。
