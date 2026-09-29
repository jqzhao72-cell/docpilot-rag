# DocPilot RAG

手写 RAG 学习项目：文档解析 → 文本切分 → Embedding → Chroma 检索 → 重排序 → Prompt → DeepSeek 问答，配有 FastAPI 后端和 Streamlit 前端。

## 目录结构

```text
manual-rag-demo/
├── app/                   # API、权限、会话和数据库模型
├── rag/                   # RAG 核心模块
│   └── ingestion/         # 文档加载、切分、论文结构解析
├── frontend/              # Streamlit 页面
├── scripts/               # 初始化、入库、模型下载、管理员设置
│   └── diagnostics/       # 数据库、用户、历史、向量库检查
├── examples/              # 手动运行的学习示例
├── tests/                 # 自动化回归测试
├── evaluation/            # 检索评估与评估数据集
├── docs/                  # 维护说明
├── data/                  # 本地文档和解析输出（不提交）
├── models/                # 本地模型（不提交）
├── chroma_db/             # 向量数据库（不提交）
├── app.db                 # SQLite 数据库（不提交）
├── requirements.txt       # 原有环境依赖快照
└── .env                   # 本地密钥（不提交）
```

## 运行约定

所有命令在项目根目录执行。脚本统一通过 `python -m 包名.模块名` 运行，确保 `app`、`rag` 导入和现有相对数据路径有效。

Windows PowerShell 激活已有环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

在本地 `.env` 中设置 `DEEPSEEK_API_KEY`。初始化数据库并启动服务：

```powershell
python -m scripts.init_db
python -m uvicorn app.main:app --reload
```

另开终端，在根目录启动前端：

```powershell
python -m streamlit run frontend/streamlit_app.py
```

接口说明：<http://127.0.0.1:8000/docs>。

## 常用工具

| 命令 | 用途 |
| --- | --- |
| `python -m scripts.ingest` | 将 `data/documents/` 文档写入向量库，会新增数据 |
| `python -m scripts.init_db` | 创建数据库表 |
| `python -m scripts.set_admin` | 将现有 ID 为 1 的用户设为管理员 |
| `python -m scripts.download_reranker` | Hugging Face 下载，沿用原本的本地 7897 代理配置 |
| `python -m scripts.download_reranker_modelscope` | ModelScope 下载 |
| `python -m scripts.diagnostics.check_chroma` | 按文件查看块数量和角色 |
| `python -m scripts.diagnostics.check_documents` | 查看向量库总量和元数据样例 |
| `python -m scripts.diagnostics.check_tables` | 查看 SQLite 表 |
| `python -m scripts.diagnostics.check_user` | 查看用户和角色 |
| `python -m scripts.diagnostics.check_history` | 查看聊天历史 |

## 学习与验证

建议学习顺序：`examples.document_loading` → `examples.text_splitting` → `examples.embedding_search` → `examples.chroma_search` → `examples.retrieval` → `examples.reranking` → `examples.prompt_building` → `examples.rag_pipeline`。

```powershell
python -m examples.prompt_building
python -m unittest discover -s tests -v
python -m evaluation.evaluate_retrieval
python -m evaluation.analyze_chunk_failures
```

`examples.model_loading` 用于检查重排序模型。加载与切分示例需要 `data/documents/test.txt`；检索与评估需要已有知识库；完整问答示例会调用 DeepSeek API。Chroma 学习示例使用独立的 `learning_demo` 集合。

## 当前限制

- `rag/reranker.py` 原有代码存在重复类定义及方法缩进问题，`Reranker.rerank` 未正确归属类，重排序调用仍需修复。
- Embedding 使用当前机器的绝对缓存路径；更换机器需要调整 `rag/embedding.py` 和 `rag/retrieval.py`。
- `requirements.txt` 为早期环境快照，未完整覆盖当前 FastAPI、Streamlit、SQLAlchemy、论文解析等依赖。此次保留原内容，未验证全新环境安装。
- 批量入库脚本沿用原实现，未写入角色元数据；需要权限隔离时使用后端上传接口。

迁移和删除明细见 [整理记录](docs/project-organization.md)。
