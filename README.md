# DocPilot

DocPilot 是一个前后端分离的论文与企业知识库 RAG 项目。后端提供 FastAPI、文档解析、混合检索、精排和 DeepSeek 问答；前端使用 Vue 3 构建登录、会话、知识库、文档和历史页面。

```text
Query → Dense + BM25 → RRF → BGE Reranker
      → Reference intent penalty → Final Top-5 → DeepSeek → Answer + Sources
```

## 工程结构

```text
DocPilot/
├── backend/                 # Python/FastAPI/RAG 工作区
│   ├── app/                 # API、权限、会话、数据库模型
│   ├── rag/                 # RAG 核心与文档解析
│   ├── scripts/             # 建库、诊断、模型和回归脚本
│   ├── tests/               # 自动化测试
│   ├── evaluation/          # 正式检索评估与评估数据
│   ├── examples/            # 学习示例和旧 Streamlit 入口
│   ├── data/                # 本地文档与解析结果（不提交）
│   ├── models/              # 本地模型（不提交）
│   ├── chroma_db/           # Chroma 数据（不提交）
│   ├── app.db               # SQLite 数据库（不提交）
│   ├── .env                 # 后端密钥（不提交）
│   └── requirements.txt
├── frontend/                # Vue 3 + Vite 正式前端
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── docs/                    # 项目级文档
├── start.ps1                # Windows 一键启动
└── README.md
```

根目录只承担项目编排；Python 命令在 `backend/` 执行，Node 命令在 `frontend/` 执行。这样现有 `app.*`、`rag.*` import 和数据相对路径都能保持稳定。

## 启动

已有依赖时，可在根目录运行：

```powershell
.\start.ps1
```

也可以分别启动。

后端：

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

- 前端：<http://127.0.0.1:5173>
- API 文档：<http://127.0.0.1:8000/docs>

详细说明见 [后端文档](backend/README.md)、[前端文档](frontend/README.md) 和 [工程整理记录](docs/project-organization.md)。
