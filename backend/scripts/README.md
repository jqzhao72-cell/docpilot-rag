# Backend Scripts

`scripts/` 只保存人工执行入口、诊断工具和回归脚本。可复用业务逻辑应放在 `rag/` 或 `app/`，而不是脚本中。

## 分类

- `init_db.py`、`set_admin.py`：数据库和管理员初始化。
- `ingest.py`、`rebuild_clean_*.py`：文档解析与索引构建。
- `download_reranker*.py`：本地模型准备。
- `diagnostics/`：SQLite、Chroma、用户和历史只读检查。
- `test_paper_*.py`、`test_hybrid_*.py`：需要真实模型和索引的手工回归。
- `diagnose_paper_reranker.py`：Reranker 输入和排序诊断。

## 运行方式

所有命令从 `backend/` 执行：

```powershell
..\.venv\Scripts\python.exe -m scripts.init_db
..\.venv\Scripts\python.exe -m scripts.test_hybrid_retrieval
..\.venv\Scripts\python.exe -m scripts.diagnostics.check_chroma
```

脚本可以解析参数、打印进度和选择输入文件，但不得重新实现 Dense、BM25、RRF、Reranker、Prompt 或 LLM 调用链。
