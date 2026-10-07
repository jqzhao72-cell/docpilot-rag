# FastAPI Application

`app/` 是 HTTP 与业务持久化适配层，不放置检索和生成算法。

| 文件 | 职责 |
| --- | --- |
| `main.py` | FastAPI 组装、CORS、路由注册和 `/chat` 编排入口 |
| `users.py` | 注册、登录和角色管理 |
| `conversations.py` | 会话与消息查询 |
| `history.py` | 兼容历史问答接口 |
| `documents.py` | 文档列表和删除 |
| `upload.py` | 上传、解析、切分、Embedding 和写入 Chroma |
| `permissions.py` | RBAC 规则 |
| `database.py` | SQLAlchemy engine/session |
| `models.py` | 用户、会话、消息和历史表模型 |

API 层通过 `rag.pipeline.PaperRAGPipeline` 复用完整问答链，不得在路由中复制 Dense、BM25、RRF、Reranker 或 Prompt 实现。后续路由数量明显增长时，可以在不改变公开 API 的前提下再拆为 `app/routes/`、`app/schemas/` 和 `app/storage/`。
