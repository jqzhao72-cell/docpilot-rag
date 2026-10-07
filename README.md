# DocPilot

DocPilot 是一个面向论文与企业知识库的前后端分离 RAG 项目。项目覆盖文档解析、结构化切分、Dense/BM25 混合检索、RRF 融合、BGE 精排、Reference 意图感知降权、DeepSeek 生成，以及带来源证据的多会话问答。

当前仓库采用 monorepo：Python/FastAPI/RAG 位于 `backend/`，Vue 3 正式前端位于 `frontend/`。本地文档、模型、Chroma 数据库、SQLite 和密钥不会提交到 Git。

## 核心功能

- 论文与企业文档解析，保留章节、页码、Figure、Table 和 chunk 元数据。
- BGE-M3 Query Embedding + Chroma cosine Dense Retrieval。
- BM25 Sparse Retrieval，增强 AKR1C3、STAT1、IRF7 等专业实体召回。
- Dense + BM25 通过 Reciprocal Rank Fusion 生成 Hybrid Top-20。
- BGE Reranker 批量精排，并保留 Dense、BM25、RRF 和 rerank 分数。
- RRF 二阶段融合，避免 Reranker 完全覆盖原始召回排序。
- Reference/Bibliography 识别与意图感知软降权；引用查询不错误压制参考文献。
- Final Top-5 构造证据 Prompt，由 DeepSeek 输出支持 `[1][2]` 引用的回答。
- 用户、角色权限、知识库上传、文档管理、会话和历史记录。
- Vue 3 企业知识工作台：登录、问答、来源证据、知识库、文档和历史页面。

## RAG 调用链

```text
Query
  ├─ BGE-M3 Dense Retrieval Top-20
  └─ BM25 Sparse Retrieval Top-20
             ↓
          RRF #1
             ↓
       Hybrid Top-20
             ↓
       BGE Reranker
             ↓
          RRF #2
             ↓
 Reference intent penalty = 4
             ↓
        Final Top-5
             ↓
   Grounded Prompt + DeepSeek
             ↓
       Answer + Sources
```

默认论文 Dense collection 为 `paper_docs_bge_m3`，使用 cosine distance；最终结果明确区分 distance 与 similarity score。完整问答入口是 `rag.pipeline.PaperRAGPipeline`。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、JavaScript、Vue Router、Pinia、Axios、CSS |
| API | FastAPI、Uvicorn、CORS |
| 数据库 | SQLite、SQLAlchemy |
| Dense Retrieval | BGE-M3、Sentence Transformers、Chroma |
| Sparse Retrieval | BM25 |
| 排序 | Reciprocal Rank Fusion、BGE Reranker |
| 文档处理 | PyMuPDF/PDF 工具、OCR、阿里云 Document Mind（可选） |
| LLM | DeepSeek API |
| 测试与评估 | unittest、自定义 Retrieval/Reranker 诊断脚本 |

## 项目结构

```text
DocPilot/
├── backend/
│   ├── app/                 # FastAPI、用户、权限、会话、文档接口
│   ├── rag/                 # 可复用 RAG 核心
│   │   └── ingestion/       # Loader、Splitter、论文结构解析
│   ├── scripts/             # 建库、诊断、模型和真实链路回归脚本
│   ├── tests/               # 自动化测试
│   ├── evaluation/          # 正式 Retrieval 评估代码与固定数据集
│   ├── examples/            # 教学示例及保留的旧 Streamlit 入口
│   ├── data/                # 本地文档、论文、解析和评估产物（不提交）
│   ├── models/              # 本地 Embedding/Reranker 模型（不提交）
│   ├── chroma_db/           # Chroma 持久化数据（不提交）
│   ├── app.db               # SQLite 数据库（不提交）
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/api/             # Axios API 封装
│   ├── src/components/      # 布局与 Sources 组件
│   ├── src/router/          # 路由与登录保护
│   ├── src/stores/          # Pinia 状态
│   ├── src/views/           # Login/Chat/Knowledge/Documents/History
│   └── package.json
├── docs/                    # 架构与项目记录
├── start.ps1                # Windows 一键启动
└── README.md
```

Python 命令需要以 `backend/` 为工作目录，Node 命令需要以 `frontend/` 为工作目录。这样 `data/`、`models/`、`chroma_db/` 和 `app.db` 的相对路径保持一致。

## 快速开始

### 1. 准备 Python 环境

示例使用仓库根目录下的 `.venv`：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 2. 配置后端

```powershell
Copy-Item backend\.env.example backend\.env
```

至少填写：

```dotenv
DEEPSEEK_API_KEY=your_api_key
```

可选配置：

- `CORS_ORIGINS`：允许访问 API 的前端地址。
- `BGE_M3_MODEL_PATH`：本地 BGE-M3 路径。
- `MINILM_MODEL_PATH`：兼容企业文档流程的本地 MiniLM 路径。
- `ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET`：可选论文云解析。
- `VISION_API_BASE/API_KEY/MODEL`：可选 Figure 视觉分析。

真实 `.env`、模型、数据和数据库均已被 `.gitignore` 排除。

### 3. 初始化数据库

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.init_db
cd ..
```

论文问答还需要本地 BGE-M3、BGE Reranker、`data/evaluation/clean_paper_chunks.json`，以及包含 940 个 clean chunks 的 `paper_docs_bge_m3` Chroma collection。模型位置可以通过环境变量覆盖。

### 4. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

开发环境 API 地址由 `frontend/.env.development` 中的 `VITE_API_BASE_URL` 提供，Vue 组件内没有硬编码后端地址。

### 5. 启动

在 Windows 根目录一键启动：

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
npm run dev
```

- 前端：<http://127.0.0.1:5173>
- FastAPI 文档：<http://127.0.0.1:8000/docs>

## 前端页面

| 页面 | 功能 |
| --- | --- |
| Login | 登录与员工注册 |
| Chat | 会话列表、问答、耗时和右侧 Sources 证据 |
| Knowledge Base | 知识库统计和按权限上传文档 |
| Documents | 文档搜索、权限展示和删除 |
| History | 用户历史问答搜索与展开 |

登录状态由 Pinia 管理，Vue Router 提供基本路由保护。Chat Sources 展示 `source`、页码范围、`section`、`chunk_type` 和原文片段。

## 主要 API

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| `POST` | `/register` | 注册 employee 用户 |
| `POST` | `/login` | 登录 |
| `PUT` | `/users/{user_id}/role` | 管理员修改角色 |
| `POST` | `/conversations` | 创建会话 |
| `GET` | `/conversations/user/{user_id}` | 用户会话列表 |
| `GET` | `/conversations/{conversation_id}/messages` | 会话消息 |
| `POST` | `/chat` | 完整 PaperRAGPipeline 问答 |
| `GET` | `/history/user/{user_id}` | 用户问答历史 |
| `GET` | `/documents` | 按权限列出文档 |
| `DELETE` | `/documents/{filename}` | 按权限删除文档 |
| `POST` | `/upload` | 上传、解析、切分并写入知识库 |

`POST /chat` 返回：

```text
answer + sources + retrieval_results + timings
```

## 测试与诊断

后端语法和自动化回归：

```powershell
cd backend
..\.venv\Scripts\python.exe -m compileall -q app rag scripts tests evaluation examples
..\.venv\Scripts\python.exe -m unittest tests.test_permissions -v
..\.venv\Scripts\python.exe -m unittest tests.test_splitter -v
```

真实模型与索引回归：

```powershell
..\.venv\Scripts\python.exe -m scripts.test_paper_retrieval
..\.venv\Scripts\python.exe -m scripts.test_hybrid_retrieval
..\.venv\Scripts\python.exe -m scripts.test_paper_reranker
..\.venv\Scripts\python.exe -m scripts.test_paper_rag_pipeline
```

前端构建：

```powershell
cd frontend
npm run build
```

## 文档导航

- [后端准备与运行](backend/README.md)
- [RAG 核心模块](backend/rag/README.md)
- [FastAPI 应用层](backend/app/README.md)
- [脚本与诊断入口](backend/scripts/README.md)
- [本地数据生命周期](backend/data/README.md)
- [Vue 前端说明](frontend/README.md)
- [工程结构整理记录](docs/project-organization.md)

## 当前边界

- 当前以文本 RAG 为主；能够解析 Figure/Table 不等于最终回答模型原生理解图片。
- 本地模型、文档、Chroma 和 SQLite 不包含在仓库中，新环境需要单独准备。
- 检索和生成质量需要结合固定评估集与人工审查，不能只用单次示例判断。
- 当前登录是本地项目级实现，生产部署前还需要密码哈希、Token、审计和更完整的安全策略。

## License

当前仓库尚未提供开源许可证。如需公开复用或分发，请先补充合适的 `LICENSE`。
