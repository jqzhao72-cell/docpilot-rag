# DocPilot 工程结构记录

## 本次前后端分离

参考 `ZY-Dong26/RAG-agent` 的 monorepo 边界，将项目整理为根目录、`backend/` 和 `frontend/` 三层：

- 原 `app/`、`rag/`、`scripts/`、`tests/`、`evaluation/`、`examples/` 移入 `backend/`。
- 原 `requirements.txt` 移入 `backend/`。
- 原 `data/`、`models/`、`chroma_db/`、`app.db`、`.env` 原样移入 `backend/`。
- 新 Vue 3 项目由 `web/` 调整为正式的 `frontend/`。
- 原 Streamlit 页面移至 `backend/examples/streamlit_app.py`，作为旧示例保留。
- 新增根目录 `start.ps1`，分别在正确工作目录启动 FastAPI 与 Vite。

没有采用参考项目的 `backend/src/rag_agent/` 深层包重构。当前项目已经稳定使用 `app.*` 与 `rag.*` import；保留包名并规定从 `backend/` 运行，能够获得清晰边界，同时避免无关的算法改写。

## 运行约束

后端代码仍使用相对于后端工作目录的路径：

- `data/`
- `models/`
- `chroma_db/`
- `app.db`
- `.env`

因此 FastAPI、测试、评估和脚本必须以 `backend/` 为当前工作目录。Vue 命令必须以 `frontend/` 为当前工作目录。

## 未修改范围

本次只调整工程边界和启动文档，没有修改 Dense、BM25、RRF、Reranker、Reference penalty、Splitter、Paper Parser、Embedding、Prompt 或 LLM 算法逻辑。
