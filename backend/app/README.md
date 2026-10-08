# FastAPI Application

`backend/app/` 是 DocPilot 的 HTTP、认证、授权、持久化和知识库适配层。API 版本为 `2.0.0`。

## 文档入口

- [完整接口参考](../../docs/api-reference.md)：每个接口的请求、响应、权限、状态码和 Swagger 操作。
- [前后端整改记录](../../docs/api-remediation.md)：认证迁移、数据流、备份和兼容策略。
- 运行时 Swagger：`http://127.0.0.1:8000/docs`
- 运行时 OpenAPI：`http://127.0.0.1:8000/openapi.json`

## 模块职责

| 文件 | 职责 |
| --- | --- |
| `main.py` | FastAPI 组装、CORS、启动迁移和 `/chat` 编排 |
| `auth.py` | scrypt 密码、8 小时可撤销 Bearer Session、认证依赖 |
| `permissions.py` | employee/hr/admin 文档 RBAC |
| `users.py` | 注册、登录、注销、当前用户、管理员用户与角色管理 |
| `conversations.py` | 当前用户会话、消息、重命名和删除 |
| `history.py` | 从 Conversation/Message 派生个人和管理员历史 |
| `documents.py` | 文档列表、上传、正文、下载、权限和删除 |
| `knowledge.py` | company/paper 适配、文档级权限过滤、实时 Dense/BM25 输入 |
| `schemas.py` | 严格请求和响应契约，拒绝额外 JSON 字段 |
| `models.py` | User、AuthSession、Conversation、Message 和迁移档案 |
| `database.py` | SQLite/SQLAlchemy engine、外键和请求级 Session |
| `migrations.py` | 备份、密码迁移、旧历史去重导入和关系约束 |

## 路由总览

| 分组 | 接口 |
| --- | --- |
| 公开 | `GET /`、`POST /register`、`POST /login` |
| 当前用户 | `GET /users/me`、`POST /logout` |
| 管理员 | `GET /users`、`PUT /users/{user_id}/role`、`GET /admin/history` |
| 会话 | `GET/POST /conversations`、`GET /conversations/{id}/messages`、`PATCH/DELETE /conversations/{id}` |
| Chat | `POST /chat` |
| 历史 | `GET /history` |
| 文档 | `GET/POST /documents`、`GET /documents/{filename}/content`、`GET /documents/{filename}/download`、`PUT /documents/{filename}/role`、`DELETE /documents/{filename}` |

## 设计边界

- 当前用户只来自 `Authorization: Bearer <token>`，不能来自请求中的 user_id。
- 会话、消息和个人历史始终限制为当前用户。
- Admin 跨用户能力使用独立管理员接口，不能绕过会话所有权。
- 前端角色判断只控制界面，后端每个接口重新认证和授权。
- 修改用户角色会撤销目标用户全部 Token。
- 缺失 role 的旧文档按 admin 处理，避免迁移时意外公开。
- `knowledge.py` 先生成授权文档集合；Dense 只查询授权 IDs，BM25 使用同一集合。
- API 层复用 `PaperRAGPipeline` 的 RRF、Reranker、Prompt 和 LLM，不复制核心算法。

## 启动与验证

在 `backend/` 中执行：

```powershell
..\.venv\Scripts\python.exe -m scripts.init_db
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

接口回归：

```powershell
..\.venv\Scripts\python.exe -m unittest tests.test_permissions tests.test_knowledge_api -v
```

首次升级旧数据库时会在 `backend/backups/` 创建备份。迁移是幂等的，后续启动不会重复导入历史。
