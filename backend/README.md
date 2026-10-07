# DocPilot Backend

后端包含 FastAPI 接口、RAG 核心、文档解析、数据索引、评估和测试。所有后端命令都应在本目录执行，以保证 `data/`、`models/`、`chroma_db/` 和 `app.db` 的相对路径一致。

## 环境准备

当前项目虚拟环境位于仓库根目录：

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

将 `.env.example` 复制为 `.env`，至少配置 `DEEPSEEK_API_KEY`。本地已有 `.env` 已随工程迁移到本目录，没有读取或改写其中内容。

## 常用命令

```powershell
# 初始化 SQLite
..\.venv\Scripts\python.exe -m scripts.init_db

# 启动 FastAPI
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 自动化测试
..\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 权限关键回归
..\.venv\Scripts\python.exe -m unittest tests.test_permissions -v

# Retrieval/RAG 手工回归
..\.venv\Scripts\python.exe -m scripts.test_hybrid_retrieval
..\.venv\Scripts\python.exe -m scripts.test_paper_rag_pipeline
```

接口文档默认位于 <http://127.0.0.1:8000/docs>。

## 目录职责

- `app/`：HTTP API、用户权限、会话、历史、文档管理和持久化。
- `rag/`：解析、切分、Embedding、Dense/BM25、RRF、Reranker、Prompt、LLM 和 Pipeline。
- `scripts/`：需要人工执行的建库、诊断和模型脚本。
- `tests/`：自动化单元与回归测试。
- `evaluation/`：正式检索评估代码和固定评估集。
- `examples/`：教学示例；`streamlit_app.py` 是保留的旧 UI，不属于正式前端。

## 代码依赖方向

参考工程的 `api → rag_agent ← scripts/devtools` 分层，本项目采用下面的依赖约束：

```text
app/ ────────────────┐
scripts/             │
evaluation/          ├──→ rag/ ──→ data / models / chroma_db
tests/               │
examples/ ───────────┘
```

- `rag/` 是可复用核心，不应反向 import `app/`、`scripts/` 或前端代码。
- `app/` 只负责 HTTP、权限和持久化适配，通过 `PaperRAGPipeline` 调用核心。
- `scripts/` 只作为人工入口，不在其中重复实现检索和问答算法。
- `evaluation/` 可以调用核心，但正式运行路径不能依赖评估代码。
- `frontend/` 只能通过 HTTP API 使用后端，不能依赖 Python 文件或本地数据库。

具体模块和公开入口见 [RAG 核心说明](rag/README.md)，脚本边界见 [脚本说明](scripts/README.md)，数据保留规则见 [数据目录说明](data/README.md)。

## 为什么暂不使用 `src/` 布局

参考项目使用 `backend/src/rag_agent/`，并由每个入口显式加入 `src` 路径。DocPilot 当前已有大量稳定的 `from rag...` 和 `from app...` 调用，直接迁移到 `src/` 会同时影响 API、脚本、测试和 IDE 配置。

目前的 `backend/rag` 与 `backend/app` 已经具备清晰包边界，因此本轮保留包名和 import。未来需要发布 Python 包或支持多后端服务时，再通过 `pyproject.toml + editable install` 完成一次独立的 `src/` 迁移，不使用临时 `sys.path` 补丁。
